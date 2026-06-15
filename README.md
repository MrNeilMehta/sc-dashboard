# Supply Chain Decision Simulation System

An end-to-end supply chain simulation platform built to demonstrate ERP-style data modeling, stochastic demand simulation, and linear programming optimization — skills directly applicable to Auger's autonomous supply chain platform.

## Live Demo
[Deployed on Vercel] → [your-url.vercel.app]

---

## What It Does

### Phase 1 — Entity Data Model (`/data`)
Models the core objects of an ERP system as typed Python dataclasses:

| Entity | Description |
|--------|-------------|
| `Supplier` | Vendor with lead time, reliability, cost, and capacity constraints |
| `InventoryNode` | Warehouse with holding cost, safety stock floor, and capacity limit |
| `PurchaseOrder` | Decision artifact linking supplier → node → quantity → date |
| `Shipment` | Physical movement of goods, linked to a purchase order |
| `DemandSignal` | Observed vs forecast demand per node per day |
| `DataGap` | Detected inconsistency in the entity graph |

The **gap detector** scans entity relationships and flags 8 classes of data quality issues:
- Orphaned shipments (no linked order)
- Shipments against cancelled orders
- Node mismatches (delivery to wrong warehouse)
- Projected negative stock (stockout certain)
- Safety stock breaches
- Missing supplier references
- Lead time violations
- Forecast error spikes (>30% deviation)

### Phase 2 — Monte Carlo Simulation (`/simulation`)
Runs 1,000 trials per node per scenario to produce a **probability distribution** over outcomes rather than a single deterministic forecast.

Each trial samples:
- Daily demand from `Normal(base × seasonality, 0.15 × base)`
- Demand spikes: 5% daily probability of 2× demand
- Supplier delivery timing based on empirical reliability rates

**Output per node:**
- P10/P50/P90 stock level trajectories
- Stockout probability per day
- Mean first-stockout day
- Service level distribution across trials
- Cost breakdown: holding vs stockout penalty

**Scenarios compared:**
1. Baseline (current orders, normal demand)
2. Stress test (3× spike frequency, 2.5× spike size)
3. Optimized (LP order plan, validated under stochastic demand)

### Phase 3 — LP Optimization (`/optimization`)

**Decision variables:** `x[s, n, t]` — units ordered from supplier `s` for node `n` on day `t`

**Objective function:**
```
min  Σ (unit_cost[s] × x[s,n,t])          # procurement cost
   + Σ (holding_cost[n] × stock[n,t])      # holding cost
   + Σ (500 × backlog[n,t])               # stockout penalty
```

**Constraints:**

| Constraint | Formula | Business meaning |
|------------|---------|-----------------|
| Inventory balance | `stock[n,t] = stock[n,t-1] + arrivals[n,t] - demand[n,t] + backlog[n,t]` | Every unit is accounted for |
| Safety stock floor | `stock[n,t] ≥ safety_stock[n]` | Never dip below buffer |
| Supplier capacity | `Σ_n x[s,n,t] ≤ capacity[s]` | Can't order more than supplier ships |
| Warehouse capacity | `stock[n,t] ≤ warehouse_cap[n]` | Physical space limit |
| Non-negativity | `x[s,n,t] ≥ 0` | Can't un-order |

**Solver:** PuLP / CBC (open-source MILP solver)
**Scale:** 5 suppliers × 3 nodes × 30 days = 450 decision variables
**Solve time:** ~0.02 seconds to global optimum

**Key result:** The LP selects cheap-but-slow BudgetSource ($7.50/unit, 10-day lead) for sustained replenishment, using fast-but-expensive suppliers only for urgent near-term coverage — the cost-vs-lead-time trade-off expressed mathematically.

---

## Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind CSS |
| Charts | Recharts |
| API | Next.js Route Handlers calling Python via `execSync` |
| LP Solver | PuLP (CBC) |
| Simulation | NumPy (Monte Carlo) |
| Deployment | Vercel |

---

## Local Setup

```bash
git clone https://github.com/your-username/sc-dashboard
cd sc-dashboard
pip install pulp numpy
npm install
npm run dev
```

Open http://localhost:3000

---

## Project Structure

```
sc-dashboard/
  app/
    page.tsx              # Overview — entity graph + gap detection
    simulate/page.tsx     # Monte Carlo simulation dashboard
    optimize/page.tsx     # LP optimizer + order plan
    api/
      overview/route.ts   # GET /api/overview
      simulate/route.ts   # GET /api/simulate
      optimize/route.ts   # GET /api/optimize
  data/
    schema.py             # Entity dataclasses
    seed_data.py          # Synthetic ERP data generator
    gap_detector.py       # 8-type gap detection engine
  simulation/
    demand.py             # Monte Carlo engine (1,000 trials)
    scenario.py           # Baseline / optimized / stress scenarios
  optimization/
    lp_model.py           # LP formulation (variables, objective, constraints)
    solver.py             # PuLP build + CBC solve + result extraction
```
