"""
Seed Data Generator
--------------------
Generates synthetic but realistic supply chain data:
  - 5 suppliers with different cost/reliability/lead-time profiles
  - 3 warehouse nodes (think: regional distribution centers)
  - 30 days of demand signals with realistic variance
  - Purchase orders and shipments with intentional data gaps
    (missing links the gap_detector will catch)

This mirrors what real ERP systems produce — messy, incomplete,
with relationships that don't always close cleanly.
"""

import random
from datetime import date, timedelta
from data.schema import (
    Supplier, InventoryNode, PurchaseOrder, Shipment,
    DemandSignal, OrderStatus, ShipmentStatus
)

random.seed(42)  # reproducible runs

START_DATE = date(2024, 1, 1)


# ── SUPPLIERS ──────────────────────────────────────────────────────────────────

def make_suppliers() -> list[Supplier]:
    return [
        Supplier(
            supplier_id="SUP-001",
            name="FastTrack Logistics",
            location="Chicago, IL",
            lead_time_days=3,
            reliability=0.95,
            unit_cost=12.50,
            capacity=500,
        ),
        Supplier(
            supplier_id="SUP-002",
            name="Global Parts Co.",
            location="Houston, TX",
            lead_time_days=7,
            reliability=0.82,
            unit_cost=9.80,
            capacity=800,
        ),
        Supplier(
            supplier_id="SUP-003",
            name="Precision Supply",
            location="Detroit, MI",
            lead_time_days=5,
            reliability=0.90,
            unit_cost=11.20,
            capacity=400,
        ),
        Supplier(
            supplier_id="SUP-004",
            name="BudgetSource Inc.",
            location="Memphis, TN",
            lead_time_days=10,
            reliability=0.70,
            unit_cost=7.50,
            capacity=1000,
        ),
        Supplier(
            supplier_id="SUP-005",
            name="PremiumGoods Ltd.",
            location="Seattle, WA",
            lead_time_days=2,
            reliability=0.98,
            unit_cost=16.00,
            capacity=200,
        ),
    ]


# ── INVENTORY NODES ────────────────────────────────────────────────────────────

def make_nodes() -> list[InventoryNode]:
    return [
        InventoryNode(
            node_id="NODE-A",
            name="East Coast DC",
            location="Newark, NJ",
            holding_cost_per_unit=0.50,
            safety_stock=100,
            capacity=2000,
            current_stock=350,
        ),
        InventoryNode(
            node_id="NODE-B",
            name="Central DC",
            location="Chicago, IL",
            holding_cost_per_unit=0.40,
            safety_stock=80,
            capacity=3000,
            current_stock=520,
        ),
        InventoryNode(
            node_id="NODE-C",
            name="West Coast DC",
            location="Los Angeles, CA",
            holding_cost_per_unit=0.60,
            safety_stock=120,
            capacity=1500,
            current_stock=210,
        ),
    ]


# ── DEMAND SIGNALS ─────────────────────────────────────────────────────────────

def make_demand_signals(nodes: list[InventoryNode], days: int = 30) -> list[DemandSignal]:
    """
    Generate 30 days of demand per node.
    Base demand varies by node size. Adds:
      - weekly seasonality (weekends ~20% lower)
      - random noise (±15%)
      - occasional demand spikes (5% chance of 2x day)
    Forecast is base demand with less noise — simulating a real forecaster
    that's pretty good but not perfect. The gap drives stockout risk.
    """
    signals = []
    base_demand = {"NODE-A": 80, "NODE-B": 110, "NODE-C": 60}

    for day_offset in range(days):
        d = START_DATE + timedelta(days=day_offset)
        weekday = d.weekday()  # 0=Mon, 6=Sun

        for node in nodes:
            base = base_demand[node.node_id]

            # seasonality
            seasonal_factor = 0.80 if weekday >= 5 else 1.0

            # spike
            spike = 2.0 if random.random() < 0.05 else 1.0

            actual = max(0, int(base * seasonal_factor * spike * random.uniform(0.85, 1.15)))
            forecast = max(0, int(base * seasonal_factor * random.uniform(0.92, 1.08)))

            signals.append(DemandSignal(
                signal_id=f"DEM-{node.node_id}-{day_offset:03d}",
                node_id=node.node_id,
                date=d,
                actual_demand=actual if day_offset < 20 else None,  # last 10 days = future
                forecast_demand=forecast,
                forecast_error=(actual - forecast) if day_offset < 20 else None,
            ))

    return signals


# ── PURCHASE ORDERS ────────────────────────────────────────────────────────────

def make_orders(suppliers: list[Supplier], nodes: list[InventoryNode]) -> list[PurchaseOrder]:
    """
    Simulate 15 purchase orders across the 30-day window.
    Intentionally includes one CANCELLED order that has a shipment
    linked to it — a data gap the detector should flag.
    """
    orders = []
    statuses = [OrderStatus.RECEIVED, OrderStatus.RECEIVED, OrderStatus.SHIPPED,
                OrderStatus.CONFIRMED, OrderStatus.PENDING]

    for i in range(15):
        sup = suppliers[i % len(suppliers)]
        node = nodes[i % len(nodes)]
        order_date = START_DATE + timedelta(days=i * 2)
        expected_date = order_date + timedelta(days=sup.lead_time_days)
        qty = random.randint(50, 200)

        status = OrderStatus.CANCELLED if i == 7 else statuses[i % len(statuses)]

        orders.append(PurchaseOrder(
            order_id=f"PO-{i+1:04d}",
            supplier_id=sup.supplier_id,
            node_id=node.node_id,
            quantity=qty,
            order_date=order_date,
            expected_date=expected_date,
            unit_cost=sup.unit_cost,
            status=status,
        ))

    return orders


# ── SHIPMENTS ──────────────────────────────────────────────────────────────────

def make_shipments(orders: list[PurchaseOrder], suppliers: list[Supplier]) -> list[Shipment]:
    """
    Generate shipments for received/shipped orders.
    Intentional data gaps introduced:
      1. One shipment linked to the CANCELLED order PO-0008 (orphaned)
      2. One shipment with no order_id at all (arrived with no paper trail)
      3. One shipment to a node that doesn't match its order's node (mismatch)
    """
    shipments = []
    sup_map = {s.supplier_id: s for s in suppliers}

    for order in orders:
        if order.status not in [OrderStatus.RECEIVED, OrderStatus.SHIPPED]:
            continue

        sup = sup_map[order.supplier_id]
        on_time = random.random() < sup.reliability
        arrival = order.expected_date if on_time else order.expected_date + timedelta(days=random.randint(1, 4))

        shipments.append(Shipment(
            shipment_id=f"SHIP-{order.order_id}",
            order_id=order.order_id,
            supplier_id=order.supplier_id,
            node_id=order.node_id,
            quantity=order.quantity,
            ship_date=order.order_date + timedelta(days=1),
            arrival_date=arrival,
            status=ShipmentStatus.DELIVERED if order.status == OrderStatus.RECEIVED else ShipmentStatus.IN_TRANSIT,
        ))

    # Gap 1: shipment linked to cancelled order PO-0008
    shipments.append(Shipment(
        shipment_id="SHIP-GAP-001",
        order_id="PO-0008",        # this order is CANCELLED — should not have a shipment
        supplier_id="SUP-002",
        node_id="NODE-B",
        quantity=75,
        ship_date=START_DATE + timedelta(days=14),
        arrival_date=START_DATE + timedelta(days=21),
        status=ShipmentStatus.DELIVERED,
    ))

    # Gap 2: orphaned shipment — no order_id at all
    shipments.append(Shipment(
        shipment_id="SHIP-GAP-002",
        order_id=None,             # arrived with no paper trail
        supplier_id="SUP-001",
        node_id="NODE-A",
        quantity=120,
        ship_date=START_DATE + timedelta(days=10),
        arrival_date=START_DATE + timedelta(days=13),
        status=ShipmentStatus.DELIVERED,
    ))

    # Gap 3: node mismatch — order was for NODE-A but shipment went to NODE-C
    shipments.append(Shipment(
        shipment_id="SHIP-GAP-003",
        order_id="PO-0001",
        supplier_id="SUP-001",
        node_id="NODE-C",          # PO-0001 is for NODE-A — mismatch
        quantity=80,
        ship_date=START_DATE + timedelta(days=3),
        arrival_date=START_DATE + timedelta(days=6),
        status=ShipmentStatus.DELIVERED,
    ))

    return shipments


# ── MASTER LOADER ──────────────────────────────────────────────────────────────

def load_all() -> dict:
    suppliers = make_suppliers()
    nodes     = make_nodes()
    orders    = make_orders(suppliers, nodes)
    shipments = make_shipments(orders, suppliers)
    signals   = make_demand_signals(nodes)

    return {
        "suppliers": suppliers,
        "nodes":     nodes,
        "orders":    orders,
        "shipments": shipments,
        "signals":   signals,
    }
