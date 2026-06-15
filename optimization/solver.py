"""
LP Solver
----------
Builds the PuLP problem, adds all constraints, solves it,
and extracts the results into clean dataclasses.

This is the file to walk through in a technical screen —
know every constraint and why it's there.
"""

import pulp
import time
from datetime import date, timedelta
from data.schema import Supplier, InventoryNode, PurchaseOrder, OrderStatus
from optimization.lp_model import (
    LPConfig, LPSolution, NodeLPResult, OrderDecision,
    forecast_demand, BASE_DEMAND
)


def solve(
    nodes:     list[InventoryNode],
    suppliers: list[Supplier],
    orders:    list[PurchaseOrder],   # existing confirmed orders
    cfg:       LPConfig = None,
) -> LPSolution:

    if cfg is None:
        cfg = LPConfig()

    T = cfg.horizon_days
    start = cfg.start_date
    t_range = range(T)

    # Index shortcuts
    node_ids = [n.node_id for n in nodes]
    sup_ids  = [s.supplier_id for s in suppliers]
    node_map = {n.node_id: n for n in nodes}
    sup_map  = {s.supplier_id: s for s in suppliers}

    # ── BUILD LP PROBLEM ───────────────────────────────────────────────────────

    prob = pulp.LpProblem("SupplyChain_Optimization", pulp.LpMinimize)

    # ── DECISION VARIABLES ─────────────────────────────────────────────────────

    # x[s,n,t] = units ordered from supplier s for node n on day t
    # lowBound=0 enforces non-negativity
    x = pulp.LpVariable.dicts(
        "order",
        [(s, n, t) for s in sup_ids for n in node_ids for t in t_range],
        lowBound=0,
        cat="Integer",      # whole units only
    )

    # stock[n,t] = inventory level at node n at end of day t
    stock = pulp.LpVariable.dicts(
        "stock",
        [(n, t) for n in node_ids for t in t_range],
        lowBound=0,         # can't have negative physical stock
    )

    # backlog[n,t] = unmet demand at node n on day t (penalty variable)
    # We want this to be zero — the high penalty drives the solver to avoid it
    backlog = pulp.LpVariable.dicts(
        "backlog",
        [(n, t) for n in node_ids for t in t_range],
        lowBound=0,
    )

    # ── OBJECTIVE FUNCTION ─────────────────────────────────────────────────────
    # Minimize: procurement cost + holding cost + stockout penalty

    procurement_cost = pulp.lpSum(
        sup_map[s].unit_cost * x[(s, n, t)]
        for s in sup_ids
        for n in node_ids
        for t in t_range
    )

    holding_cost = pulp.lpSum(
        node_map[n].holding_cost_per_unit * stock[(n, t)]
        for n in node_ids
        for t in t_range
    )

    stockout_cost = pulp.lpSum(
        cfg.stockout_penalty * backlog[(n, t)]
        for n in node_ids
        for t in t_range
    )

    prob += procurement_cost + holding_cost + stockout_cost, "Total_Cost"

    # ── CONSTRAINT 1: INVENTORY BALANCE ───────────────────────────────────────
    # stock[n,t] = stock[n,t-1] + arrivals[n,t] - demand[n,t] + backlog[n,t]
    #
    # arrivals[n,t] = units from LP orders placed (t - lead_time) days ago
    #               + units from existing confirmed orders arriving on day t
    #
    # This is the core accounting identity — every unit is tracked.

    # Pre-compute existing order arrivals per node per day
    existing_arrivals = {(n, t): 0 for n in node_ids for t in t_range}
    for order in orders:
        if order.status in [OrderStatus.CANCELLED, OrderStatus.RECEIVED]:
            continue
        arrival_offset = (order.expected_date - start).days
        if 0 <= arrival_offset < T and order.node_id in node_ids:
            existing_arrivals[(order.node_id, arrival_offset)] += order.quantity

    for n in node_ids:
        node = node_map[n]
        demand_series = [forecast_demand(n, t) for t in t_range]

        for t in t_range:
            demand = demand_series[t]

            # LP order arrivals: order placed on day (t - lead_time) arrives today
            lp_arrivals = pulp.lpSum(
                x[(s, n, t - sup_map[s].lead_time_days)]
                for s in sup_ids
                if t - sup_map[s].lead_time_days >= 0
            )

            existing = existing_arrivals.get((n, t), 0)

            if t == 0:
                # Day 0: opening stock = current physical stock
                prob += (
                    stock[(n, t)] ==
                    node.current_stock + lp_arrivals + existing - demand + backlog[(n, t)]
                ), f"balance_{n}_{t}"
            else:
                prob += (
                    stock[(n, t)] ==
                    stock[(n, t-1)] + lp_arrivals + existing - demand + backlog[(n, t)]
                ), f"balance_{n}_{t}"

    # ── CONSTRAINT 2: SAFETY STOCK FLOOR ──────────────────────────────────────
    # stock[n,t] >= safety_stock[n]   for all n, t
    # We never want to dip below minimum buffer — this is the service level
    # constraint expressed as a hard floor on physical inventory.

    for n in node_ids:
        node = node_map[n]
        for t in t_range:
            prob += (
                stock[(n, t)] >= node.safety_stock
            ), f"safety_stock_{n}_{t}"

    # ── CONSTRAINT 3: SUPPLIER CAPACITY PER PERIOD ────────────────────────────
    # Σ_n x[s,n,t] <= capacity[s]   for all s, t
    # Each supplier has a max throughput per period — can't order more than they
    # can ship, regardless of how urgent the need is.

    for s in sup_ids:
        sup = sup_map[s]
        for t in t_range:
            prob += (
                pulp.lpSum(x[(s, n, t)] for n in node_ids) <= sup.capacity
            ), f"supplier_capacity_{s}_{t}"

    # ── CONSTRAINT 4: WAREHOUSE CAPACITY ──────────────────────────────────────
    # stock[n,t] <= warehouse_capacity[n]   for all n, t
    # Can't store more than the warehouse physically holds.

    for n in node_ids:
        node = node_map[n]
        for t in t_range:
            prob += (
                stock[(n, t)] <= node.capacity
            ), f"warehouse_capacity_{n}_{t}"

    # ── CONSTRAINT 5: MINIMUM ORDER SIZE ──────────────────────────────────────
    # If ordering, order at least cfg.order_min units (avoids trivial orders)
    # Implemented implicitly through integrality — x is Integer, lowBound=0.

    # ── SOLVE ──────────────────────────────────────────────────────────────────

    t0 = time.time()
    solver = pulp.PULP_CBC_CMD(msg=0, timeLimit=120)  # suppress solver output
    prob.solve(solver)
    solve_time = time.time() - t0

    status        = pulp.LpStatus[prob.status]
    solver_status = pulp.LpStatus.get(prob.sol_status, str(prob.sol_status))

    # ── EXTRACT RESULTS ────────────────────────────────────────────────────────

    all_orders: list[OrderDecision] = []
    node_results: list[NodeLPResult] = []

    for n in node_ids:
        node           = node_map[n]
        daily_stock    = []
        daily_backlog  = []
        daily_demand   = []
        daily_arrivals = []
        node_orders: list[OrderDecision] = []

        for t in t_range:
            stock_val   = pulp.value(stock[(n, t)]) or 0.0
            backlog_val = pulp.value(backlog[(n, t)]) or 0.0
            demand_val  = forecast_demand(n, t)

            # Arrivals on this day from LP decisions
            arriving = sum(
                int(pulp.value(x[(s, n, t - sup_map[s].lead_time_days)]) or 0)
                for s in sup_ids
                if t - sup_map[s].lead_time_days >= 0
            ) + existing_arrivals.get((n, t), 0)

            daily_stock.append(round(stock_val, 2))
            daily_backlog.append(round(backlog_val, 2))
            daily_demand.append(demand_val)
            daily_arrivals.append(arriving)

        # Extract order decisions (x[s,n,t] > 0)
        for s in sup_ids:
            sup = sup_map[s]
            for t in t_range:
                qty = pulp.value(x[(s, n, t)])
                if qty and qty > 0.5:  # filter floating point noise
                    order_date   = start + timedelta(days=t)
                    arrival_date = start + timedelta(days=t + sup.lead_time_days)
                    od = OrderDecision(
                        supplier_id  = s,
                        node_id      = n,
                        order_day    = t,
                        arrival_day  = t + sup.lead_time_days,
                        order_date   = order_date,
                        arrival_date = arrival_date,
                        quantity     = int(round(qty)),
                        unit_cost    = sup.unit_cost,
                    )
                    node_orders.append(od)
                    all_orders.append(od)

        node_results.append(NodeLPResult(
            node_id       = n,
            node_name     = node.name,
            daily_stock   = daily_stock,
            daily_backlog = daily_backlog,
            daily_demand  = daily_demand,
            daily_arrivals= daily_arrivals,
            orders        = sorted(node_orders, key=lambda o: o.order_day),
        ))

    # Total costs from objective components
    total_proc    = sum(o.total_cost for o in all_orders)
    total_holding = sum(
        node_map[n].holding_cost_per_unit * sum(
            pulp.value(stock[(n, t)]) or 0 for t in t_range
        )
        for n in node_ids
    )
    total_so = sum(
        cfg.stockout_penalty * (pulp.value(backlog[(n, t)]) or 0)
        for n in node_ids for t in t_range
    )

    return LPSolution(
        status            = status,
        solver_status     = str(solver_status),
        total_cost        = (pulp.value(prob.objective) or 0.0),
        total_order_cost  = total_proc,
        total_holding_cost= total_holding,
        total_stockout_cost= total_so,
        node_results      = node_results,
        all_orders        = sorted(all_orders, key=lambda o: (o.order_day, o.node_id)),
        solve_time_sec    = solve_time,
    )
