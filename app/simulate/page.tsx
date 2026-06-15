"use client";
import { useEffect, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, Legend,
  ResponsiveContainer, ReferenceLine, Area, AreaChart
} from "recharts";

interface DayPoint { day: number; p10: number; p50: number; p90: number; stockout_prob: number }
interface NodeResult {
  node_id: string; node_name: string;
  stockout_probability: number; mean_service_level: number; p10_service_level: number;
  mean_first_stockout_day: number | null;
  mean_total_cost: number; mean_holding_cost: number; mean_stockout_cost: number;
  daily_stock_p10: number[]; daily_stock_p50: number[]; daily_stock_p90: number[];
  daily_stockout_prob: number[];
  stress_stockout_probability: number; stress_mean_total_cost: number;
}
interface SimData { nodes: NodeResult[]; n_trials: number; horizon: number }

const NODE_COLORS: Record<string, string> = { "NODE-A": "#3b82f6", "NODE-B": "#8b5cf6", "NODE-C": "#10b981" };

export default function SimulatePage() {
  const [data, setData] = useState<SimData | null>(null);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState("NODE-A");

  const runSim = () => {
    setLoading(true);
    fetch("/api/simulate").then(r => r.json()).then(d => { setData(d); setLoading(false); });
  };

  const node = data?.nodes.find(n => n.node_id === selected);

  const chartData: DayPoint[] = node
    ? node.daily_stock_p50.map((p50, i) => ({
        day: i + 1,
        p10: Math.round(node.daily_stock_p10[i]),
        p50: Math.round(p50),
        p90: Math.round(node.daily_stock_p90[i]),
        stockout_prob: Math.round(node.daily_stockout_prob[i] * 100),
      }))
    : [];

  return (
    <div className="space-y-8">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Demand simulation</h1>
          <p className="text-sm text-gray-500 mt-1">
            Phase 2 — Monte Carlo simulation across 1,000 trials × 30 days per node.
          </p>
        </div>
        <button
          onClick={runSim}
          disabled={loading}
          className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm px-4 py-2 rounded-lg transition-colors"
        >
          {loading ? "Running 1,000 trials…" : "Run simulation"}
        </button>
      </div>

      {!data && !loading && (
        <div className="bg-white border border-gray-100 rounded-xl p-16 text-center">
          <div className="text-gray-400 text-sm">Click "Run simulation" to execute Monte Carlo across all nodes</div>
        </div>
      )}

      {loading && (
        <div className="bg-white border border-gray-100 rounded-xl p-16 text-center">
          <div className="text-blue-500 text-sm animate-pulse">Simulating 3,000 trial-node combinations…</div>
        </div>
      )}

      {data && (
        <>
          {/* Node summary cards */}
          <div className="grid grid-cols-3 gap-4">
            {data.nodes.map(n => (
              <button
                key={n.node_id}
                onClick={() => setSelected(n.node_id)}
                className={`text-left bg-white border rounded-xl p-4 transition-all ${
                  selected === n.node_id ? "border-blue-400 ring-1 ring-blue-200" : "border-gray-100 hover:border-gray-200"
                }`}
              >
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm font-medium text-gray-900">{n.node_name}</span>
                  <span
                    className="text-xs px-2 py-0.5 rounded-full font-medium"
                    style={{
                      background: n.stockout_probability > 0.5 ? "#fee2e2" : "#fef3c7",
                      color: n.stockout_probability > 0.5 ? "#b91c1c" : "#92400e"
                    }}
                  >
                    {Math.round(n.stockout_probability * 100)}% stockout risk
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs text-gray-500">
                  <div>Service level<br /><span className="text-gray-900 font-medium">{Math.round(n.mean_service_level * 100)}%</span></div>
                  <div>First stockout<br /><span className="text-gray-900 font-medium">{n.mean_first_stockout_day ? `Day ${Math.round(n.mean_first_stockout_day)}` : "—"}</span></div>
                  <div>Monthly cost<br /><span className="text-gray-900 font-medium">${Math.round(n.mean_total_cost).toLocaleString()}</span></div>
                  <div>Stress cost<br /><span className="text-red-600 font-medium">${Math.round(n.stress_mean_total_cost).toLocaleString()}</span></div>
                </div>
              </button>
            ))}
          </div>

          {/* Stock distribution chart */}
          {node && (
            <div className="grid grid-cols-2 gap-6">
              <div className="bg-white border border-gray-100 rounded-xl p-5">
                <h2 className="text-sm font-medium text-gray-700 mb-1">Stock level distribution — {node.node_name}</h2>
                <p className="text-xs text-gray-400 mb-4">P10/P50/P90 across 1,000 trials</p>
                <ResponsiveContainer width="100%" height={240}>
                  <AreaChart data={chartData}>
                    <XAxis dataKey="day" tick={{ fontSize: 11 }} label={{ value: "Day", position: "insideBottom", offset: -2, fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip formatter={(v) => [`${Number(v)} units`]} />
                    <Area type="monotone" dataKey="p90" stroke="none" fill="#dbeafe" name="P90 (optimistic)" />
                    <Area type="monotone" dataKey="p50" stroke="#3b82f6" fill="#bfdbfe" name="P50 (median)" strokeWidth={2} />
                    <Area type="monotone" dataKey="p10" stroke="none" fill="#fff" name="P10 (pessimistic)" />
                    <ReferenceLine y={0} stroke="#ef4444" strokeDasharray="3 3" label={{ value: "Stockout", fontSize: 10, fill: "#ef4444" }} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>

              <div className="bg-white border border-gray-100 rounded-xl p-5">
                <h2 className="text-sm font-medium text-gray-700 mb-1">Daily stockout probability — {node.node_name}</h2>
                <p className="text-xs text-gray-400 mb-4">% of trials with stockout on each day</p>
                <ResponsiveContainer width="100%" height={240}>
                  <AreaChart data={chartData}>
                    <XAxis dataKey="day" tick={{ fontSize: 11 }} label={{ value: "Day", position: "insideBottom", offset: -2, fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} unit="%" domain={[0, 100]} />
                    <Tooltip formatter={(v) => [`${Number(v)}%`]} />
                    <ReferenceLine y={5}  stroke="#f59e0b" strokeDasharray="3 3" label={{ value: "5%", fontSize: 10, fill: "#f59e0b" }} />
                    <ReferenceLine y={50} stroke="#ef4444" strokeDasharray="3 3" label={{ value: "50%", fontSize: 10, fill: "#ef4444" }} />
                    <Area type="monotone" dataKey="stockout_prob" stroke="#ef4444" fill="#fee2e2" name="Stockout risk" strokeWidth={2} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
