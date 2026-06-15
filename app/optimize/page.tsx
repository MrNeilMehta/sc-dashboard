"use client";
import { useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  LineChart, Line, ReferenceLine, Legend
} from "recharts";

interface OrderDecision {
  supplier_id: string; node_id: string;
  order_day: number; arrival_day: number;
  order_date: string; arrival_date: string;
  quantity: number; unit_cost: number; total_cost: number;
}
interface NodeResult {
  node_id: string; node_name: string;
  service_level: number; min_stock: number; min_stock_day: number;
  total_order_cost: number; total_holding_cost: number;
  order_count: number;
  daily_stock: number[]; daily_demand: number[]; daily_arrivals: number[];
}
interface LPData {
  status: string; solve_time: number;
  total_cost: number; total_order_cost: number;
  total_holding_cost: number; total_stockout_cost: number;
  total_orders: number;
  node_results: NodeResult[];
  all_orders: OrderDecision[];
  supplier_names: Record<string, string>;
}

const NODE_COLORS: Record<string, string> = { "NODE-A": "#3b82f6", "NODE-B": "#8b5cf6", "NODE-C": "#10b981" };

export default function OptimizePage() {
  const [data, setData] = useState<LPData | null>(null);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState("NODE-A");

  const runLP = () => {
    setLoading(true);
    fetch("/api/optimize").then(r => r.json()).then(d => { setData(d); setLoading(false); });
  };

  const node = data?.node_results.find(n => n.node_id === selected);

  const stockChart = node
    ? node.daily_stock.map((s, i) => ({
        day: i + 1,
        stock: Math.round(s),
        demand: node.daily_demand[i],
        arrivals: node.daily_arrivals[i],
      }))
    : [];

  const supplierSpend = data
    ? Object.entries(
        data.all_orders.reduce((acc, o) => {
          const name = data.supplier_names[o.supplier_id] || o.supplier_id;
          acc[name] = (acc[name] || 0) + o.total_cost;
          return acc;
        }, {} as Record<string, number>)
      ).map(([name, cost]) => ({ name: name.split(" ")[0], cost: Math.round(cost) }))
    : [];

  return (
    <div className="space-y-8">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">LP optimizer</h1>
          <p className="text-sm text-gray-500 mt-1">
            Phase 3 — Linear programming minimizes procurement + holding + stockout cost across 450 decision variables.
          </p>
        </div>
        <button
          onClick={runLP}
          disabled={loading}
          className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm px-4 py-2 rounded-lg transition-colors"
        >
          {loading ? "Solving LP…" : "Run optimizer"}
        </button>
      </div>

      {!data && !loading && (
        <div className="bg-white border border-gray-100 rounded-xl p-16 text-center space-y-3">
          <div className="text-gray-400 text-sm">Click "Run optimizer" to solve the LP</div>
          <div className="text-xs text-gray-300 max-w-md mx-auto">
            Minimizes: procurement cost + holding cost + stockout penalty<br/>
            Subject to: inventory balance · safety stock · supplier capacity · warehouse limits
          </div>
        </div>
      )}

      {loading && (
        <div className="bg-white border border-gray-100 rounded-xl p-16 text-center">
          <div className="text-blue-500 text-sm animate-pulse">CBC solver running… building 450 decision variables</div>
        </div>
      )}

      {data && (
        <>
          {/* Solution summary */}
          <div className="grid grid-cols-4 gap-3">
            {[
              { label: "Solver status", value: data.status, green: data.status === "Optimal" },
              { label: "Solve time",    value: `${data.solve_time.toFixed(2)}s` },
              { label: "Total orders",  value: data.total_orders },
              { label: "Total cost",    value: `$${Math.round(data.total_cost).toLocaleString()}` },
            ].map(({ label, value, green }) => (
              <div key={label} className="bg-white border border-gray-100 rounded-xl p-4">
                <div className={`text-xl font-semibold ${green ? "text-green-600" : "text-gray-900"}`}>{value}</div>
                <div className="text-xs text-gray-500 mt-1">{label}</div>
              </div>
            ))}
          </div>

          {/* Cost breakdown + supplier spend */}
          <div className="grid grid-cols-2 gap-6">
            <div className="bg-white border border-gray-100 rounded-xl p-5">
              <h2 className="text-sm font-medium text-gray-700 mb-4">Cost breakdown (30-day horizon)</h2>
              <div className="space-y-3">
                {[
                  { label: "Procurement", value: data.total_order_cost, color: "bg-blue-400" },
                  { label: "Holding",     value: data.total_holding_cost, color: "bg-purple-400" },
                  { label: "Stockout penalty", value: data.total_stockout_cost, color: "bg-red-400" },
                ].map(({ label, value, color }) => {
                  const pct = Math.round((value / data.total_cost) * 100);
                  return (
                    <div key={label}>
                      <div className="flex justify-between text-xs text-gray-600 mb-1">
                        <span>{label}</span>
                        <span className="font-medium">${Math.round(value).toLocaleString()} ({pct}%)</span>
                      </div>
                      <div className="w-full bg-gray-100 rounded-full h-2">
                        <div className={`h-2 rounded-full ${color}`} style={{ width: `${pct}%` }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="bg-white border border-gray-100 rounded-xl p-5">
              <h2 className="text-sm font-medium text-gray-700 mb-4">Spend by supplier</h2>
              <ResponsiveContainer width="100%" height={160}>
                <BarChart data={supplierSpend}>
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} tickFormatter={v => `$${(v/1000).toFixed(0)}k`} />
                  <Tooltip formatter={(v) => [`$${Number(v).toLocaleString()}`]} />
                  <Bar dataKey="cost" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Node tabs */}
          <div>
            <div className="flex gap-2 mb-4">
              {data.node_results.map(n => (
                <button
                  key={n.node_id}
                  onClick={() => setSelected(n.node_id)}
                  className={`text-sm px-4 py-1.5 rounded-lg border transition-all ${
                    selected === n.node_id
                      ? "bg-blue-50 border-blue-300 text-blue-700"
                      : "bg-white border-gray-200 text-gray-600 hover:border-gray-300"
                  }`}
                >
                  {n.node_name}
                </button>
              ))}
            </div>

            {node && (
              <div className="grid grid-cols-2 gap-6">
                <div className="bg-white border border-gray-100 rounded-xl p-5">
                  <div className="flex items-center justify-between mb-1">
                    <h2 className="text-sm font-medium text-gray-700">Optimal stock trajectory — {node.node_name}</h2>
                    <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">
                      SL {Math.round(node.service_level * 100)}%
                    </span>
                  </div>
                  <p className="text-xs text-gray-400 mb-4">Daily stock, demand, and incoming supply</p>
                  <ResponsiveContainer width="100%" height={220}>
                    <LineChart data={stockChart}>
                      <XAxis dataKey="day" tick={{ fontSize: 11 }} />
                      <YAxis tick={{ fontSize: 11 }} />
                      <Tooltip />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                      <Line type="monotone" dataKey="stock"    stroke="#3b82f6" strokeWidth={2} dot={false} name="Stock" />
                      <Line type="monotone" dataKey="demand"   stroke="#ef4444" strokeWidth={1} strokeDasharray="4 2" dot={false} name="Demand" />
                      <Line type="monotone" dataKey="arrivals" stroke="#10b981" strokeWidth={1} dot={false} name="Arrivals" />
                    </LineChart>
                  </ResponsiveContainer>
                </div>

                <div className="bg-white border border-gray-100 rounded-xl p-5">
                  <h2 className="text-sm font-medium text-gray-700 mb-3">Order plan — {node.node_name}</h2>
                  <div className="flex gap-3 mb-4 text-xs text-gray-500">
                    <span>{node.order_count} orders</span>
                    <span>·</span>
                    <span>${Math.round(node.total_order_cost).toLocaleString()} procurement</span>
                    <span>·</span>
                    <span>${Math.round(node.total_holding_cost).toLocaleString()} holding</span>
                  </div>
                  <div className="overflow-y-auto max-h-48 space-y-1.5">
                    {data.all_orders
                      .filter(o => o.node_id === selected)
                      .map((o, i) => (
                        <div key={i} className="flex items-center justify-between text-xs border border-gray-100 rounded-lg px-3 py-2">
                          <div>
                            <span className="font-medium text-gray-800">
                              {(data.supplier_names[o.supplier_id] || o.supplier_id).split(" ")[0]}
                            </span>
                            <span className="text-gray-400 ml-2">Day {o.order_day} → Day {o.arrival_day}</span>
                          </div>
                          <div className="text-right">
                            <span className="font-medium text-gray-800">{o.quantity} units</span>
                            <span className="text-gray-400 ml-2">${o.total_cost.toLocaleString()}</span>
                          </div>
                        </div>
                      ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
