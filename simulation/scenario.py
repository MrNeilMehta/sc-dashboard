"""
Scenario Runner
----------------
Runs three simulation scenarios side by side so the dashboard can
show the value of optimization vs doing nothing.

SCENARIO 1 — Baseline (do nothing):
  Current stock + existing orders + uncertain demand.
  Shows the stockout risk you're carrying right now.

SCENARIO 2 — Optimized (post-LP):
  Same demand uncertainty, but supply schedule is replaced with
  the LP optimizer's recommended order plan.
  Shows how much the optimizer reduces stockout risk and cost.

SCENARIO 3 — Stress test (demand spike):
  Same as baseline but spike probability tripled (15%) and
  spike multiplier increased to 2.5x.
  Tests resilience under supply chain disruption.
"""

from dataclasses import dataclass
from datetime import date
from data.schema import InventoryNode, Supplier, PurchaseOrder
from simulation.demand import (
    SimulationConfig, NodeSimulationResult, run_simulation
)


@dataclass
class ScenarioComparison:
    node_id:   str
    node_name: str
    baseline:  NodeSimulationResult
    optimized: NodeSimulationResult | None  # populated after Phase 3 LP runs
    stress:    NodeSimulationResult

    def stockout_reduction(self) -> float | None:
        """How much the optimizer reduces stockout probability vs baseline."""
        if self.optimized is None:
            return None
        return self.baseline.stockout_probability - self.optimized.stockout_probability

    def cost_reduction(self) -> float | None:
        """$ saved per 30-day horizon by following the LP plan."""
        if self.optimized is None:
            return None
        return self.baseline.mean_total_cost - self.optimized.mean_total_cost


def run_all_scenarios(
    nodes:      list[InventoryNode],
    orders:     list[PurchaseOrder],
    suppliers:  list[Supplier],
    start_date: date = date(2024, 1, 1),
    optimized_orders: list[PurchaseOrder] | None = None,
) -> list[ScenarioComparison]:

    # Scenario 1 — Baseline
    baseline_cfg = SimulationConfig(n_trials=1000, horizon_days=30)
    baseline_results = run_simulation(nodes, orders, suppliers, start_date, baseline_cfg)

    # Scenario 2 — Optimized (uses LP orders if available, else None)
    if optimized_orders is not None:
        opt_cfg     = SimulationConfig(n_trials=1000, horizon_days=30)
        opt_results = run_simulation(nodes, optimized_orders, suppliers, start_date, opt_cfg)
        opt_map     = {r.node_id: r for r in opt_results}
    else:
        opt_map = {}

    # Scenario 3 — Stress test
    stress_cfg = SimulationConfig(
        n_trials          = 1000,
        horizon_days      = 30,
        spike_probability = 0.15,   # 3x normal spike frequency
        spike_multiplier  = 2.5,    # bigger spikes
        stockout_penalty  = 75.0,   # higher penalty (expediting gets expensive)
    )
    stress_results = run_simulation(nodes, orders, suppliers, start_date, stress_cfg)

    # Build comparison objects
    baseline_map = {r.node_id: r for r in baseline_results}
    stress_map   = {r.node_id: r for r in stress_results}

    comparisons = []
    for node in nodes:
        comparisons.append(ScenarioComparison(
            node_id   = node.node_id,
            node_name = node.name,
            baseline  = baseline_map[node.node_id],
            optimized = opt_map.get(node.node_id),
            stress    = stress_map[node.node_id],
        ))

    return comparisons
