"""
Phase 3 Validation Runner
--------------------------
Solves the LP and prints the full order plan + cost breakdown.
Run from project root: python run_phase3.py
"""

import sys
sys.path.insert(0, ".")

from data.seed_data import load_all
from optimization.lp_model import LPConfig
from optimization.solver import solve


def bar(value: float, max_val: float, width: int = 25) -> str:
    filled = int((value / max_val) * width) if max_val > 0 else 0
    filled = min(filled, width)
    return "█" * filled + "░" * (width - filled)


def main():
    print("=" * 68)
    print("SUPPLY CHAIN SIMULATION — PHASE 3")
    print("Linear Programming Optimization (PuLP / CBC solver)")
    print("=" * 68)

    data = load_all()
    cfg  = LPConfig(horizon_days=30, stockout_penalty=500.0)

    print("\n Solving LP...")
    solution = solve(
        nodes     = data["nodes"],
        suppliers = data["suppliers"],
        orders    = data["orders"],
        cfg       = cfg,
    )

    print(f" Status        : {solution.status}")
    print(f" Solve time    : {solution.solve_time_sec:.2f}s")
    print(f" Total orders  : {len(solution.all_orders)}")

    print(f"\n{'─'*68}")
    print(f"  COST SUMMARY (30-day horizon)")
    print(f"{'─'*68}")
    print(f"  Procurement cost  : ${solution.total_order_cost:>10,.0f}")
    print(f"  Holding cost      : ${solution.total_holding_cost:>10,.0f}")
    print(f"  Stockout penalty  : ${solution.total_stockout_cost:>10,.0f}")
    print(f"  {'─'*36}")
    print(f"  TOTAL             : ${solution.total_cost:>10,.0f}")

    for nr in solution.node_results:
        print(f"\n{'─'*68}")
        print(f"  NODE: {nr.node_name} ({nr.node_id})")
        print(f"{'─'*68}")
        print(f"  Service level     : {nr.service_level:.1%}")
        min_day, min_s = nr.min_stock_day
        print(f"  Min stock         : {min_s:.0f} units on day {min_day}")
        print(f"  Orders placed     : {len(nr.orders)}")
        print(f"  Total order cost  : ${nr.total_order_cost:,.0f}")

        if nr.orders:
            print(f"\n  ORDER PLAN:")
            print(f"  {'Day':<5} {'Supplier':<26} {'Qty':>5} {'$/unit':>7} {'Arrives':>8} {'Cost':>9}")
            print(f"  {'─'*64}")
            for o in nr.orders:
                from data.seed_data import make_suppliers
                sup_name = {s.supplier_id: s.name for s in make_suppliers()}
                print(
                    f"  {o.order_day:<5} {sup_name.get(o.supplier_id, o.supplier_id):<26} "
                    f"{o.quantity:>5} ${o.unit_cost:>6.2f} "
                    f"  Day {o.arrival_day:<4} ${o.total_cost:>8,.0f}"
                )

        # Daily stock chart
        print(f"\n  PROJECTED DAILY STOCK (safety stock floor = {data['nodes'][[n.node_id for n in data['nodes']].index(nr.node_id)].safety_stock if False else '—'})")
        print(f"  Day  Stock   Demand  Arrivals  Chart")
        print(f"  {'─'*60}")
        node_obj = next(n for n in data["nodes"] if n.node_id == nr.node_id)
        for i, (s, d, arr) in enumerate(zip(nr.daily_stock, nr.daily_demand, nr.daily_arrivals)):
            stock_bar = bar(s, node_obj.capacity, width=20)
            safety_marker = " ⚠" if s <= node_obj.safety_stock else ""
            arr_str = f"+{arr}" if arr > 0 else ""
            print(f"  {i:<4} {s:>6.0f}   {d:>5}   {arr_str:>8}  [{stock_bar}]{safety_marker}")

    print(f"\n{'═'*68}")
    print("Phase 3 complete. LP produces optimal order plan.")
    print("Ready for Phase 4: Next.js frontend + API.")
    print(f"{'═'*68}\n")


if __name__ == "__main__":
    main()
