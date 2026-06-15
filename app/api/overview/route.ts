import { NextResponse } from "next/server";
import { execSync } from "child_process";
import path from "path";

export async function GET() {
  const root = path.join(process.cwd());
  const result = execSync(
    `python3 -c "
import sys; sys.path.insert(0,'.')
from data.seed_data import load_all
from data.gap_detector import detect_gaps, summarise_gaps
import json, dataclasses
from datetime import date

data = load_all()
gaps = detect_gaps(data['suppliers'], data['nodes'], data['orders'], data['shipments'], data['signals'])
summary = summarise_gaps(gaps)

def to_dict(obj):
    if dataclasses.is_dataclass(obj):
        d = {}
        for f in dataclasses.fields(obj):
            v = getattr(obj, f.name)
            d[f.name] = to_dict(v)
        return d
    if hasattr(obj, 'value'): return obj.value
    if isinstance(obj, list): return [to_dict(i) for i in obj]
    if isinstance(obj, date): return str(obj)
    return obj

out = {
    'entities': {
        'suppliers': len(data['suppliers']),
        'nodes': len(data['nodes']),
        'orders': len(data['orders']),
        'shipments': len(data['shipments']),
        'signals': len(data['signals']),
    },
    'nodes': [{'node_id': n.node_id, 'name': n.name, 'current_stock': n.current_stock,
               'capacity': n.capacity, 'safety_stock': n.safety_stock}
              for n in data['nodes']],
    'gaps': {
        'total': summary['total'],
        'critical': summary['critical'],
        'warning': summary['warning'],
        'info': summary['info'],
        'by_type': summary['by_type'],
        'gaps': [to_dict(g) for g in summary['gaps']],
    }
}
print(json.dumps(out))
"`,
    { cwd: root, encoding: "utf8" }
  );
  return NextResponse.json(JSON.parse(result));
}
