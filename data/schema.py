"""
Supply Chain Entity Data Model
--------------------------------
Defines the core entities that mirror an ERP system:
  Supplier → PurchaseOrder → Shipment → InventoryNode → DemandSignal

Each entity is a Python dataclass — lightweight, typed, and easy to
serialize to JSON for the API layer later.
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import date
from enum import Enum


class OrderStatus(Enum):
    PENDING   = "pending"
    CONFIRMED = "confirmed"
    SHIPPED   = "shipped"
    RECEIVED  = "received"
    CANCELLED = "cancelled"


class ShipmentStatus(Enum):
    IN_TRANSIT = "in_transit"
    DELAYED    = "delayed"
    DELIVERED  = "delivered"


@dataclass
class Supplier:
    """
    Represents a vendor in the procurement network.

    lead_time_days: how long from order to delivery (used as LP constraint)
    reliability:    0.0–1.0 probability of on-time delivery (used in simulation)
    unit_cost:      cost per unit ordered (used in LP objective)
    capacity:       max units this supplier can ship per period (LP constraint)
    """
    supplier_id:    str
    name:           str
    location:       str
    lead_time_days: int
    reliability:    float       # 0.0 – 1.0
    unit_cost:      float       # $ per unit
    capacity:       int         # max units per period


@dataclass
class InventoryNode:
    """
    A warehouse or distribution center holding stock.

    holding_cost_per_unit: $ per unit per day sitting in the warehouse (LP objective)
    safety_stock:          minimum units to always keep on hand (LP constraint)
    capacity:              max units the warehouse can hold (LP constraint)
    current_stock:         units on hand right now (simulation starting state)
    """
    node_id:               str
    name:                  str
    location:              str
    holding_cost_per_unit: float   # $ per unit per day
    safety_stock:          int     # minimum stock floor
    capacity:              int     # max storage
    current_stock:         int     # current on-hand units


@dataclass
class PurchaseOrder:
    """
    An order placed to a supplier for a specific node.
    This is the decision variable the LP will optimize:
    how many units to order, from which supplier, for which node, when.
    """
    order_id:       str
    supplier_id:    str
    node_id:        str
    quantity:       int
    order_date:     date
    expected_date:  date
    unit_cost:      float
    status:         OrderStatus = OrderStatus.PENDING

    @property
    def total_cost(self) -> float:
        return self.quantity * self.unit_cost


@dataclass
class Shipment:
    """
    A physical movement of goods from supplier to node.
    Linked to a PurchaseOrder — a missing link here is a data gap.
    """
    shipment_id:    str
    order_id:       Optional[str]   # None = data gap (orphaned shipment)
    supplier_id:    str
    node_id:        str
    quantity:       int
    ship_date:      date
    arrival_date:   date
    status:         ShipmentStatus = ShipmentStatus.IN_TRANSIT


@dataclass
class DemandSignal:
    """
    Observed or forecasted demand at a node on a given day.
    actual_demand:    what customers actually pulled (historical)
    forecast_demand:  what the model predicted
    This gap between actual vs forecast is what drives stockout risk.
    """
    signal_id:       str
    node_id:         str
    date:            date
    actual_demand:   Optional[int]  # None for future dates (forecast only)
    forecast_demand: int
    forecast_error:  Optional[float] = None  # actual - forecast, populated post-hoc


@dataclass
class DataGap:
    """
    A detected inconsistency or missing link in the entity graph.
    The gap_detector produces these — this is what Auger's ontology work does:
    finding where the data model doesn't match reality.
    """
    gap_id:       str
    entity_type:  str       # "shipment", "order", "inventory", etc.
    entity_id:    str
    gap_type:     str       # "missing_link", "negative_stock", "orphaned_shipment", etc.
    description:  str
    severity:     str       # "critical", "warning", "info"
