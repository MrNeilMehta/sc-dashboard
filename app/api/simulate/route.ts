import { NextResponse } from "next/server";
import { execSync } from "child_process";
import path from "path";

export async function GET() {
  const root = path.join(process.cwd());
  const result = execSync(
    `python3 -c "
import sys; sys.path.insert(0,'.')
from data.seed_data import load_all
from simulation.scenario import run_all_scenarios
import json

data = load_all()
scenarios = run_all_scenarios(nodes=data['nodes'], orders=data['orders'], suppliers=data['suppliers'])

nodes_out = []
for sc in scenarios:
    b = sc.baseline
    s = sc.stress
    nodes_out.append({
        'node_id': b.node_id,
        'node_name': b.node_name,
        'stockout_probability': round(b.stockout_probability, 4),
        'mean_service_level': round(b.mean_service_level, 4),
        'p10_service_level': round(b.p10_service_level, 4),
        'mean_first_stockout_day': round(b.mean_first_stockout_day, 1) if b.mean_first_stockout_day else None,
        'mean_total_cost': round(b.mean_total_cost, 0),
        'mean_holding_cost': round(b.mean_holding_cost, 0),
        'mean_stockout_cost': round(b.mean_stockout_cost, 0),
        'daily_stock_p10': b.daily_stock_p10,
        'daily_stock_p50': b.daily_stock_p50,
        'daily_stock_p90': b.daily_stock_p90,
        'daily_stockout_prob': b.daily_stockout_prob,
        'stress_stockout_probability': round(s.stockout_probability, 4),
        'stress_mean_total_cost': round(s.mean_total_cost, 0),
    })

print(json.dumps({'nodes': nodes_out, 'n_trials': 1000, 'horizon': 30}))
"`,
    { cwd: root, encoding: "utf8", timeout: 120000 }
  );
  return NextResponse.json(JSON.parse(result));
}
