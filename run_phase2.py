"""
Phase 2 Validation Runner
--------------------------
Runs Monte Carlo simulation and prints results.
Run from project root: python run_phase2.py
"""

import sys
sys.path.insert(0, ".")

from data.seed_data import load_all
from simulation.scenario import run_all_scenarios


def bar(value: float, width: int = 20, max_val: float = 1.0) -> str:
    filled = int((value / max_val) * width)
    filled = min(filled, width)
    return "█" * filled + "░" * (width - filled)


def main():
    print("=" * 65)
    print("SUPPLY CHAIN SIMULATION — PHASE 2")
    print("Monte Carlo Demand Simulation (1,000 trials × 30 days)")
    print("=" * 65)

    data      = load_all()
    scenarios = run_all_scenarios(
        nodes     = data["nodes"],
        orders    = data["orders"],
        suppliers = data["suppliers"],
    )

    for sc in scenarios:
        b = sc.baseline
        s = sc.stress

        print(f"\n{'─'*65}")
        print(f"  NODE: {b.node_name} ({b.node_id})")
        print(f"{'─'*65}")

        print(f"\n  BASELINE SCENARIO (current orders, normal demand)")
        print(f"    Stockout probability  : {bar(b.stockout_probability)} {b.stockout_probability:.1%}")
        print(f"    Mean service level    : {bar(b.mean_service_level)}  {b.mean_service_level:.1%}")
        print(f"    P10 service level     : {bar(b.p10_service_level)}  {b.p10_service_level:.1%}  (worst 10% of scenarios)")
        if b.mean_first_stockout_day is not None:
            print(f"    First stockout on avg : Day {b.mean_first_stockout_day:.1f} of 30")
        print(f"    Mean total cost/month : ${b.mean_total_cost:,.0f}")
        print(f"      Holding cost        : ${b.mean_holding_cost:,.0f}")
        print(f"      Stockout penalty    : ${b.mean_stockout_cost:,.0f}")

        print(f"\n  STRESS TEST SCENARIO (3x spike freq, 2.5x spike size)")
        print(f"    Stockout probability  : {bar(s.stockout_probability)} {s.stockout_probability:.1%}")
        print(f"    Mean service level    : {bar(s.mean_service_level)}  {s.mean_service_level:.1%}")
        print(f"    Mean total cost/month : ${s.mean_total_cost:,.0f}  (+${s.mean_total_cost - b.mean_total_cost:,.0f} vs baseline)")

        print(f"\n  DAILY STOCKOUT RISK (baseline) — P(stockout) by day")
        # Print a compact risk heatmap across 30 days
        risk_line = ""
        for prob in b.daily_stockout_prob:
            if prob < 0.05:
                risk_line += "·"
            elif prob < 0.20:
                risk_line += "▒"
            elif prob < 0.50:
                risk_line += "▓"
            else:
                risk_line += "█"
        print(f"    Days 1-30: [{risk_line}]")
        print(f"    Legend: · <5%  ▒ 5-20%  ▓ 20-50%  █ >50%")

    print(f"\n{'═'*65}")
    print("Phase 2 complete. Ready for Phase 3: LP Optimization Engine.")
    print(f"{'═'*65}\n")


if __name__ == "__main__":
    main()
