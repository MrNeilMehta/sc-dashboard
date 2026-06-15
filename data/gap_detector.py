"""
Gap Detector
-------------
Scans the entity graph for inconsistencies, missing links, and
business-process violations. This is the core of bullet 3:

  "Developed entity-level data model linking orders, shipments,
   suppliers, and inventory states to identify data gaps and simulate
   downstream operational impact under uncertainty."

Gap types detected:
  1. orphaned_shipment      — shipment with no order_id
  2. cancelled_order_ship   — shipment linked to a cancelled order
  3. node_mismatch          — shipment delivered to wrong node vs order
  4. negative_stock         — inventory would go below zero given demand
  5. below_safety_stock     — stock at or below safety stock floor
  6. missing_supplier       — order references a supplier_id not in master list
  7. lead_time_breach       — order expected_date impossible given lead time
  8. forecast_error_spike   — single-day forecast error > 30% (bad model signal)
"""

from data.schema import (
    Supplier, InventoryNode, PurchaseOrder, Shipment,
    DemandSignal, DataGap, OrderStatus
)
from datetime import timedelta
from typing import Optional


def detect_gaps(
    suppliers: list[Supplier],
    nodes: list[InventoryNode],
    orders: list[PurchaseOrder],
    shipments: list[Shipment],
    signals: list[DemandSignal],
) -> list[DataGap]:

    gaps: list[DataGap] = []
    gap_counter = 0

    def new_gap(entity_type, entity_id, gap_type, description, severity) -> DataGap:
        nonlocal gap_counter
        gap_counter += 1
        return DataGap(
            gap_id=f"GAP-{gap_counter:04d}",
            entity_type=entity_type,
            entity_id=entity_id,
            gap_type=gap_type,
            description=description,
            severity=severity,
        )

    # Build lookup maps for fast cross-referencing
    supplier_ids  = {s.supplier_id for s in suppliers}
    node_ids      = {n.node_id for n in nodes}
    order_map     = {o.order_id: o for o in orders}
    node_map      = {n.node_id: n for n in nodes}

    # ── 1. SHIPMENT CHECKS ─────────────────────────────────────────────────────

    for ship in shipments:

        # Gap type: orphaned shipment — no order_id
        if ship.order_id is None:
            gaps.append(new_gap(
                entity_type="shipment",
                entity_id=ship.shipment_id,
                gap_type="orphaned_shipment",
                description=(
                    f"Shipment {ship.shipment_id} from supplier {ship.supplier_id} "
                    f"to {ship.node_id} has no linked purchase order. "
                    f"Quantity {ship.quantity} units received with no paper trail."
                ),
                severity="critical",
            ))
            continue  # no order to cross-check further

        order = order_map.get(ship.order_id)

        # Gap type: shipment references non-existent order
        if order is None:
            gaps.append(new_gap(
                entity_type="shipment",
                entity_id=ship.shipment_id,
                gap_type="missing_order",
                description=(
                    f"Shipment {ship.shipment_id} references order {ship.order_id} "
                    f"which does not exist in the order master."
                ),
                severity="critical",
            ))
            continue

        # Gap type: shipment against a cancelled order
        if order.status == OrderStatus.CANCELLED:
            gaps.append(new_gap(
                entity_type="shipment",
                entity_id=ship.shipment_id,
                gap_type="cancelled_order_shipment",
                description=(
                    f"Shipment {ship.shipment_id} is linked to order {ship.order_id} "
                    f"which has status CANCELLED. {ship.quantity} units may have been "
                    f"received incorrectly or billed without authorisation."
                ),
                severity="critical",
            ))

        # Gap type: shipment delivered to wrong node
        if order.node_id != ship.node_id:
            gaps.append(new_gap(
                entity_type="shipment",
                entity_id=ship.shipment_id,
                gap_type="node_mismatch",
                description=(
                    f"Shipment {ship.shipment_id} was delivered to {ship.node_id} "
                    f"but order {ship.order_id} was placed for {order.node_id}. "
                    f"{ship.quantity} units are in the wrong location."
                ),
                severity="warning",
            ))

    # ── 2. ORDER CHECKS ────────────────────────────────────────────────────────

    for order in orders:

        # Gap type: order references unknown supplier
        if order.supplier_id not in supplier_ids:
            gaps.append(new_gap(
                entity_type="order",
                entity_id=order.order_id,
                gap_type="missing_supplier",
                description=(
                    f"Order {order.order_id} references supplier {order.supplier_id} "
                    f"which is not in the supplier master list."
                ),
                severity="critical",
            ))

        # Gap type: expected delivery date is impossible given supplier lead time
        supplier = next((s for s in suppliers if s.supplier_id == order.supplier_id), None)
        if supplier:
            min_expected = order.order_date + timedelta(days=supplier.lead_time_days)
            if order.expected_date < min_expected:
                gaps.append(new_gap(
                    entity_type="order",
                    entity_id=order.order_id,
                    gap_type="lead_time_breach",
                    description=(
                        f"Order {order.order_id} expected delivery {order.expected_date} "
                        f"is earlier than minimum possible ({min_expected}) given "
                        f"supplier {supplier.name}'s {supplier.lead_time_days}-day lead time."
                    ),
                    severity="warning",
                ))

    # ── 3. INVENTORY CHECKS ────────────────────────────────────────────────────

    # Aggregate actual demand per node over the historical window
    demand_by_node: dict[str, int] = {}
    for sig in signals:
        if sig.actual_demand is not None:
            demand_by_node[sig.node_id] = demand_by_node.get(sig.node_id, 0) + sig.actual_demand

    # Aggregate received quantity per node from delivered shipments
    received_by_node: dict[str, int] = {}
    for ship in shipments:
        from data.schema import ShipmentStatus
        if ship.status == ShipmentStatus.DELIVERED and ship.order_id is not None:
            received_by_node[ship.node_id] = received_by_node.get(ship.node_id, 0) + ship.quantity

    for node in nodes:
        total_demand   = demand_by_node.get(node.node_id, 0)
        total_received = received_by_node.get(node.node_id, 0)
        projected_stock = node.current_stock + total_received - total_demand

        # Gap type: stock would go negative
        if projected_stock < 0:
            gaps.append(new_gap(
                entity_type="inventory",
                entity_id=node.node_id,
                gap_type="negative_stock",
                description=(
                    f"Node {node.name} ({node.node_id}): projected stock is "
                    f"{projected_stock} units after {total_demand} units demand "
                    f"and {total_received} units received. Stockout likely."
                ),
                severity="critical",
            ))

        # Gap type: stock at or below safety stock floor
        elif projected_stock <= node.safety_stock:
            gaps.append(new_gap(
                entity_type="inventory",
                entity_id=node.node_id,
                gap_type="below_safety_stock",
                description=(
                    f"Node {node.name} ({node.node_id}): projected stock "
                    f"{projected_stock} units is at or below safety stock "
                    f"floor of {node.safety_stock} units."
                ),
                severity="warning",
            ))

    # ── 4. DEMAND SIGNAL CHECKS ────────────────────────────────────────────────

    for sig in signals:
        if sig.actual_demand is not None and sig.forecast_error is not None:
            error_pct = abs(sig.forecast_error) / max(sig.forecast_demand, 1)
            if error_pct > 0.30:
                gaps.append(new_gap(
                    entity_type="demand_signal",
                    entity_id=sig.signal_id,
                    gap_type="forecast_error_spike",
                    description=(
                        f"Signal {sig.signal_id} on {sig.date} at node {sig.node_id}: "
                        f"forecast error of {sig.forecast_error:+d} units "
                        f"({error_pct:.0%} deviation). Actual={sig.actual_demand}, "
                        f"Forecast={sig.forecast_demand}."
                    ),
                    severity="warning",
                ))

    return gaps


# ── SUMMARY REPORT ─────────────────────────────────────────────────────────────

def summarise_gaps(gaps: list[DataGap]) -> dict:
    """Returns a structured summary for the API / dashboard."""
    by_severity = {"critical": [], "warning": [], "info": []}
    by_type: dict[str, int] = {}

    for gap in gaps:
        by_severity[gap.severity].append(gap)
        by_type[gap.gap_type] = by_type.get(gap.gap_type, 0) + 1

    return {
        "total": len(gaps),
        "critical": len(by_severity["critical"]),
        "warning":  len(by_severity["warning"]),
        "info":     len(by_severity["info"]),
        "by_type":  by_type,
        "gaps":     gaps,
    }
