"""
LP Optimization Model
----------------------
This is the mathematical heart of the project.

THE PROBLEM IN PLAIN ENGLISH:
  We have 3 warehouses running out of stock in under 4 days.
  We have 5 suppliers with different costs, lead times, and capacities.
  We need to decide: how many units to order, from which supplier,
  for which warehouse, on which day — to keep all warehouses stocked
  above their safety stock floor for 30 days, at minimum total cost.

THE MATH:

  DECISION VARIABLES:
    x[s, n, t] = units ordered from supplier s, for node n, on day t
    b[n, t]    = backlog (units short) at node n on day t  (we want this = 0)

  OBJECTIVE — minimize total cost:
    min  Σ (order_cost[s] × x[s,n,t])          ← procurement cost
       + Σ (holding_cost[n] × stock[n,t])       ← holding cost
       + Σ (stockout_penalty × b[n,t])          ← penalty for any shortfall

  CONSTRAINTS:
    1. Inventory balance per node per day:
         stock[n,t] = stock[n,t-1] + arrivals[n,t] - demand[n,t] + b[n,t]
         (stock can't go negative — backlog variable absorbs the gap)

    2. Safety stock floor:
         stock[n,t] >= safety_stock[n]   for all n, t

    3. Supplier capacity per period:
         Σ_n x[s,n,t] <= capacity[s]    for all s, t

    4. Node warehouse capacity:
         stock[n,t] <= warehouse_capacity[n]   for all n, t

    5. Order quantities non-negative integers:
         x[s,n,t] >= 0

    6. Service level target (soft constraint via penalty):
         The stockout penalty is set high enough that the solver
         naturally avoids backlog — equivalent to a 95%+ service level.

  WHY LINEAR PROGRAMMING:
    All constraints are linear inequalities. The objective is a linear
    sum. PuLP's CBC solver finds the global optimum in seconds.
    This is faster and more reliable than heuristic methods for this
    problem size (5 suppliers × 3 nodes × 30 days = 450 variables).
"""

import pulp
from dataclasses import dataclass, field
from datetime import date, timedelta
from data.schema import Supplier, InventoryNode, PurchaseOrder, OrderStatus


# ── LP CONFIG ──────────────────────────────────────────────────────────────────

@dataclass
class LPConfig:
    horizon_days:     int   = 30
    stockout_penalty: float = 500.0   # $/unit short — high to enforce service level
    service_level:    float = 0.95    # target (enforced via penalty magnitude)
    order_min:        int   = 0       # minimum order quantity
    start_date:       date  = None

    def __post_init__(self):
        if self.start_date is None:
            self.start_date = date(2024, 1, 1)


# ── DEMAND FORECAST (deterministic mean for LP) ────────────────────────────────

BASE_DEMAND = {"NODE-A": 80, "NODE-B": 110, "NODE-C": 60}

def forecast_demand(node_id: str, day: int) -> int:
    """
    LP uses deterministic (mean) demand — we optimize against the expected
    demand signal. The simulation then stress-tests the LP plan against
    stochastic demand to validate robustness.
    Includes weekday seasonality, no noise (LP needs fixed coefficients).
    """
    base    = BASE_DEMAND.get(node_id, 80)
    weekday = day % 7
    factor  = 0.80 if weekday >= 5 else 1.0
    return int(base * factor)


# ── LP RESULT DATACLASSES ─────────────────────────────────────────────────────

@dataclass
class OrderDecision:
    """A single order recommended by the LP."""
    supplier_id:   str
    node_id:       str
    order_day:     int
    arrival_day:   int
    order_date:    date
    arrival_date:  date
    quantity:      int
    unit_cost:     float

    @property
    def total_cost(self) -> float:
        return self.quantity * self.unit_cost


@dataclass
class NodeLPResult:
    """LP results for a single node."""
    node_id:          str
    node_name:        str
    daily_stock:      list[float]       # projected stock each day
    daily_backlog:    list[float]       # units short each day (should be ~0)
    daily_demand:     list[int]         # deterministic demand used
    daily_arrivals:   list[int]         # units arriving from LP orders
    orders:           list[OrderDecision] = field(default_factory=list)

    @property
    def total_order_cost(self) -> float:
        return sum(o.total_cost for o in self.orders)

    @property
    def total_holding_cost(self) -> float:
        return sum(s * 0.50 for s in self.daily_stock)  # simplified flat rate

    @property
    def total_stockout_cost(self) -> float:
        return sum(b * 500.0 for b in self.daily_backlog)

    @property
    def service_level(self) -> float:
        days_without_stockout = sum(1 for b in self.daily_backlog if b < 0.01)
        return days_without_stockout / len(self.daily_backlog)

    @property
    def min_stock_day(self) -> tuple[int, float]:
        min_stock = min(self.daily_stock)
        min_day   = self.daily_stock.index(min_stock)
        return min_day, min_stock


@dataclass
class LPSolution:
    """Full LP solution across all nodes."""
    status:           str
    solver_status:    str
    total_cost:       float
    total_order_cost: float
    total_holding_cost: float
    total_stockout_cost: float
    node_results:     list[NodeLPResult]
    all_orders:       list[OrderDecision]
    solve_time_sec:   float

    @property
    def is_optimal(self) -> bool:
        return self.status == "Optimal"
