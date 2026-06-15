"""
Demand Simulation Engine
--------------------------
Monte Carlo simulation of demand uncertainty across inventory nodes.

WHY MONTE CARLO:
  Real demand is never exactly what you forecast. A single forecast
  line gives you one scenario. Running 1000 trials with randomised
  demand each time gives you a probability distribution — you can say
  "there's a 23% chance NODE-A stocksout in the next 10 days" rather
  than "demand will be exactly 80 units/day."

WHAT IT MODELS:
  - Base demand per node per day
  - Weekly seasonality (weekends ~20% lower)
  - Random noise drawn from a normal distribution
  - Demand spikes (random high-demand events, e.g. promotions)
  - Supplier delivery uncertainty (on-time vs delayed by lead time)
  - Starting stock + incoming shipments as supply

OUTPUT PER TRIAL:
  - Daily stock levels across the 30-day horizon
  - Stockout events (day, node, units short)
  - Service level achieved (% of demand days with stock > 0)
  - Total holding cost (stock on hand × holding cost rate)
  - Total stockout penalty cost (units short × penalty rate)
"""

import random
import numpy as np
from dataclasses import dataclass, field
from datetime import date, timedelta
from data.schema import InventoryNode, Supplier, PurchaseOrder, DemandSignal, ShipmentStatus, OrderStatus


# ── SIMULATION PARAMETERS ──────────────────────────────────────────────────────

@dataclass
class SimulationConfig:
    n_trials:          int   = 1000    # number of Monte Carlo trials
    horizon_days:      int   = 30      # planning horizon
    stockout_penalty:  float = 50.0    # $ per unit short (lost sale + expediting cost)
    demand_std_pct:    float = 0.15    # demand noise std dev as % of mean (15%)
    spike_probability: float = 0.05    # 5% chance per day of a demand spike
    spike_multiplier:  float = 2.0     # spike demand = base × this


# ── PER-TRIAL RESULT ───────────────────────────────────────────────────────────

@dataclass
class DayState:
    day:           int
    date:          date
    node_id:       str
    opening_stock: int
    demand:        int
    supply:        int          # units arriving this day from shipments/orders
    closing_stock: int
    stockout_units: int         # units of unmet demand (0 if no stockout)
    holding_cost:  float
    stockout_cost: float


@dataclass
class TrialResult:
    trial_id:        int
    node_id:         str
    day_states:      list[DayState] = field(default_factory=list)

    @property
    def total_holding_cost(self) -> float:
        return sum(d.holding_cost for d in self.day_states)

    @property
    def total_stockout_cost(self) -> float:
        return sum(d.stockout_cost for d in self.day_states)

    @property
    def total_cost(self) -> float:
        return self.total_holding_cost + self.total_stockout_cost

    @property
    def stockout_days(self) -> int:
        return sum(1 for d in self.day_states if d.stockout_units > 0)

    @property
    def service_level(self) -> float:
        """% of days demand was fully met"""
        total = len(self.day_states)
        if total == 0:
            return 1.0
        return (total - self.stockout_days) / total

    @property
    def first_stockout_day(self) -> int | None:
        for d in self.day_states:
            if d.stockout_units > 0:
                return d.day
        return None


# ── NODE-LEVEL SIMULATION SUMMARY ─────────────────────────────────────────────

@dataclass
class NodeSimulationResult:
    node_id:                  str
    node_name:                str
    n_trials:                 int
    stockout_probability:     float       # % of trials with at least one stockout
    mean_service_level:       float       # average service level across trials
    p10_service_level:        float       # 10th percentile (pessimistic scenario)
    mean_first_stockout_day:  float | None  # avg day of first stockout (if any)
    mean_total_cost:          float
    mean_holding_cost:        float
    mean_stockout_cost:       float
    daily_stock_p10:          list[float]   # pessimistic daily stock (10th pct)
    daily_stock_p50:          list[float]   # median daily stock
    daily_stock_p90:          list[float]   # optimistic daily stock (90th pct)
    daily_stockout_prob:      list[float]   # P(stockout) on each day


# ── DEMAND SAMPLER ─────────────────────────────────────────────────────────────

BASE_DEMAND = {
    "NODE-A": 80,
    "NODE-B": 110,
    "NODE-C": 60,
}

def sample_demand(node_id: str, day_offset: int, cfg: SimulationConfig) -> int:
    """
    Draw a single demand sample for a node on a given day.
    Combines: base demand × seasonality × spike × gaussian noise
    """
    base = BASE_DEMAND.get(node_id, 80)

    # Weekly seasonality — weekends ~20% lower
    # day_offset 0 = Jan 1 2024 = Monday
    weekday = day_offset % 7
    seasonal = 0.80 if weekday >= 5 else 1.0

    # Spike event
    spike = cfg.spike_multiplier if random.random() < cfg.spike_probability else 1.0

    # Gaussian noise — std dev = demand_std_pct × base
    mean   = base * seasonal * spike
    std    = base * cfg.demand_std_pct
    sample = int(np.random.normal(mean, std))

    return max(0, sample)


# ── SUPPLY SCHEDULE ────────────────────────────────────────────────────────────

def build_supply_schedule(
    node_id:   str,
    orders:    list[PurchaseOrder],
    suppliers: list[Supplier],
    start_date: date,
    horizon:   int,
    reliable_mode: bool = False,  # True = always on time (optimistic), False = probabilistic
) -> dict[int, int]:
    """
    Returns a dict mapping day_offset → units arriving that day.
    Supplier reliability determines whether each shipment arrives on time
    or is delayed by 1-4 days.
    """
    schedule: dict[int, int] = {d: 0 for d in range(horizon)}
    sup_map = {s.supplier_id: s for s in suppliers}

    for order in orders:
        if order.node_id != node_id:
            continue
        if order.status in [OrderStatus.CANCELLED, OrderStatus.RECEIVED]:
            continue

        sup = sup_map.get(order.supplier_id)
        if sup is None:
            continue

        # Determine arrival day
        if reliable_mode or random.random() < sup.reliability:
            arrival_date = order.expected_date
        else:
            delay = random.randint(1, 4)
            arrival_date = order.expected_date + timedelta(days=delay)

        day_offset = (arrival_date - start_date).days
        if 0 <= day_offset < horizon:
            schedule[day_offset] = schedule.get(day_offset, 0) + order.quantity

    return schedule


# ── SINGLE TRIAL ───────────────────────────────────────────────────────────────

def run_single_trial(
    trial_id:   int,
    node:       InventoryNode,
    orders:     list[PurchaseOrder],
    suppliers:  list[Supplier],
    start_date: date,
    cfg:        SimulationConfig,
) -> TrialResult:

    supply_schedule = build_supply_schedule(
        node.node_id, orders, suppliers, start_date, cfg.horizon_days
    )

    result = TrialResult(trial_id=trial_id, node_id=node.node_id)
    stock = node.current_stock

    for day in range(cfg.horizon_days):
        current_date  = start_date + timedelta(days=day)
        opening_stock = stock
        supply        = supply_schedule.get(day, 0)
        stock        += supply
        demand        = sample_demand(node.node_id, day, cfg)

        if stock >= demand:
            stock          -= demand
            stockout_units  = 0
        else:
            stockout_units  = demand - stock
            stock           = 0

        holding_cost  = stock * node.holding_cost_per_unit
        stockout_cost = stockout_units * cfg.stockout_penalty

        result.day_states.append(DayState(
            day            = day,
            date           = current_date,
            node_id        = node.node_id,
            opening_stock  = opening_stock,
            demand         = demand,
            supply         = supply,
            closing_stock  = stock,
            stockout_units = stockout_units,
            holding_cost   = holding_cost,
            stockout_cost  = stockout_cost,
        ))

    return result


# ── FULL MONTE CARLO RUN ───────────────────────────────────────────────────────

def run_simulation(
    nodes:      list[InventoryNode],
    orders:     list[PurchaseOrder],
    suppliers:  list[Supplier],
    start_date: date = date(2024, 1, 1),
    cfg:        SimulationConfig = None,
) -> list[NodeSimulationResult]:

    if cfg is None:
        cfg = SimulationConfig()

    all_results: list[NodeSimulationResult] = []

    for node in nodes:
        trials: list[TrialResult] = []

        for t in range(cfg.n_trials):
            trial = run_single_trial(t, node, orders, suppliers, start_date, cfg)
            trials.append(trial)

        # ── Aggregate across trials ────────────────────────────────────────────

        stockout_trials = [t for t in trials if t.stockout_days > 0]
        stockout_prob   = len(stockout_trials) / cfg.n_trials

        service_levels  = [t.service_level for t in trials]
        mean_sl         = float(np.mean(service_levels))
        p10_sl          = float(np.percentile(service_levels, 10))

        first_so_days   = [t.first_stockout_day for t in stockout_trials]
        mean_first_so   = float(np.mean(first_so_days)) if first_so_days else None

        total_costs     = [t.total_cost for t in trials]
        holding_costs   = [t.total_holding_cost for t in trials]
        stockout_costs  = [t.total_stockout_cost for t in trials]

        # Daily stock distribution across all trials
        daily_stocks = np.array([
            [day.closing_stock for day in t.day_states]
            for t in trials
        ])  # shape: (n_trials, horizon_days)

        daily_p10 = np.percentile(daily_stocks, 10, axis=0).tolist()
        daily_p50 = np.percentile(daily_stocks, 50, axis=0).tolist()
        daily_p90 = np.percentile(daily_stocks, 90, axis=0).tolist()

        # P(stockout on day d) = fraction of trials with stockout_units > 0 on day d
        daily_so_flags = np.array([
            [1 if day.stockout_units > 0 else 0 for day in t.day_states]
            for t in trials
        ])
        daily_so_prob = np.mean(daily_so_flags, axis=0).tolist()

        all_results.append(NodeSimulationResult(
            node_id               = node.node_id,
            node_name             = node.name,
            n_trials              = cfg.n_trials,
            stockout_probability  = stockout_prob,
            mean_service_level    = mean_sl,
            p10_service_level     = p10_sl,
            mean_first_stockout_day = mean_first_so,
            mean_total_cost       = float(np.mean(total_costs)),
            mean_holding_cost     = float(np.mean(holding_costs)),
            mean_stockout_cost    = float(np.mean(stockout_costs)),
            daily_stock_p10       = [round(v, 1) for v in daily_p10],
            daily_stock_p50       = [round(v, 1) for v in daily_p50],
            daily_stock_p90       = [round(v, 1) for v in daily_p90],
            daily_stockout_prob   = [round(v, 4) for v in daily_so_prob],
        ))

    return all_results
