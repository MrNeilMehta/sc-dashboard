import { NextResponse } from "next/server";
import { execSync } from "child_process";
import path from "path";

export async function GET() {
  const root = path.join(process.cwd());
  const result = execSync(
    `python3 -c "
import sys; sys.path.insert(0,'.')
from data.seed_data import load_all, make_suppliers
from optimization.lp_model import LPConfig
from optimization.solver import solve
import json

data = load_all()
cfg  = LPConfig(horizon_days=30, stockout_penalty=500.0)
sol  = solve(nodes=data['nodes'], suppliers=data['suppliers'], orders=data['orders'], cfg=cfg)

sup_names = {s.supplier_id: s.name for s in make_suppliers()}

node_results = []
for nr in sol.node_results:
    min_day, min_s = nr.min_stock_day
    node_results.append({
        'node_id': nr.node_id,
        'node_name': nr.node_name,
        'service_level': round(nr.service_level, 4),
        'min_stock': round(min_s),
        'min_stock_day': min_day,
        'total_order_cost': round(nr.total_order_cost),
        'total_holding_cost': round(nr.total_holding_cost),
        'order_count': len(nr.orders),
        'daily_stock': [round(s) for s in nr.daily_stock],
        'daily_demand': nr.daily_demand,
        'daily_arrivals': nr.daily_arrivals,
    })

all_orders = [{
    'supplier_id': o.supplier_id,
    'node_id': o.node_id,
    'order_day': o.order_day,
    'arrival_day': o.arrival_day,
    'order_date': str(o.order_date),
    'arrival_date': str(o.arrival_date),
    'quantity': o.quantity,
    'unit_cost': o.unit_cost,
    'total_cost': round(o.total_cost),
} for o in sol.all_orders]

out = {
    'status': sol.status,
    'solve_time': round(sol.solve_time_sec, 3),
    'total_cost': round(sol.total_cost),
    'total_order_cost': round(sol.total_order_cost),
    'total_holding_cost': round(sol.total_holding_cost),
    'total_stockout_cost': round(sol.total_stockout_cost),
    'total_orders': len(sol.all_orders),
    'node_results': node_results,
    'all_orders': all_orders,
    'supplier_names': sup_names,
}
print(json.dumps(out))
"`,
    { cwd: root, encoding: "utf8", timeout: 60000 }
  );
  return NextResponse.json(JSON.parse(result));
}
