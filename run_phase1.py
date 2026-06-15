"""
Phase 1 Validation Runner
--------------------------
Loads seed data, runs the gap detector, and prints a clean summary.
Run from the project root: python run_phase1.py
"""

import sys
sys.path.insert(0, ".")

from data.seed_data import load_all
from data.gap_detector import detect_gaps, summarise_gaps


def main():
    print("=" * 60)
    print("SUPPLY CHAIN SIMULATION — PHASE 1")
    print("Entity Data Model + Gap Detection")
    print("=" * 60)

    # Load all entities
    data = load_all()
    suppliers = data["suppliers"]
    nodes     = data["nodes"]
    orders    = data["orders"]
    shipments = data["shipments"]
    signals   = data["signals"]

    print(f"\n ENTITIES LOADED")
    print(f"  Suppliers      : {len(suppliers)}")
    print(f"  Inventory nodes: {len(nodes)}")
    print(f"  Purchase orders: {len(orders)}")
    print(f"  Shipments      : {len(shipments)}")
    print(f"  Demand signals : {len(signals)}")

    print(f"\n INVENTORY SNAPSHOT")
    for node in nodes:
        pct = node.current_stock / node.capacity * 100
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        print(f"  {node.name:<20} [{bar}] {node.current_stock:>4} / {node.capacity} units ({pct:.0f}%)")

    print(f"\n SUPPLIER PROFILES")
    for sup in suppliers:
        print(f"  {sup.name:<25} lead={sup.lead_time_days}d  reliability={sup.reliability:.0%}  cost=${sup.unit_cost:.2f}/unit  cap={sup.capacity}")

    # Run gap detection
    gaps = detect_gaps(suppliers, nodes, orders, shipments, signals)
    summary = summarise_gaps(gaps)

    print(f"\n GAP DETECTION RESULTS")
    print(f"  Total gaps found : {summary['total']}")
    print(f"  Critical         : {summary['critical']}")
    print(f"  Warning          : {summary['warning']}")

    print(f"\n GAPS BY TYPE")
    for gap_type, count in summary["by_type"].items():
        print(f"  {gap_type:<30} {count}")

    print(f"\n CRITICAL GAPS (action required)")
    for gap in summary["gaps"]:
        if gap.severity == "critical":
            print(f"\n  [{gap.gap_id}] {gap.gap_type.upper()}")
            print(f"  Entity : {gap.entity_type} / {gap.entity_id}")
            print(f"  Detail : {gap.description}")

    print(f"\n WARNINGS")
    for gap in summary["gaps"]:
        if gap.severity == "warning":
            print(f"\n  [{gap.gap_id}] {gap.gap_type.upper()}")
            print(f"  Entity : {gap.entity_type} / {gap.entity_id}")
            print(f"  Detail : {gap.description}")

    print("\n" + "=" * 60)
    print("Phase 1 complete. Ready for Phase 2: Demand Simulation.")
    print("=" * 60)


if __name__ == "__main__":
    main()
