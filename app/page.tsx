"use client";
import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";

interface GapSummary {
  total: number; critical: number; warning: number; info: number;
  by_type: Record<string, number>;
  gaps: Array<{ gap_id: string; entity_type: string; entity_id: string; gap_type: string; description: string; severity: string }>;
}
interface Entity {
  suppliers: number; nodes: number; orders: number; shipments: number; signals: number;
}
interface NodeSnap {
  node_id: string; name: string; current_stock: number; capacity: number; safety_stock: number;
}
interface OverviewData { entities: Entity; nodes: NodeSnap[]; gaps: GapSummary }

export default function OverviewPage() {
  const [data, setData] = useState<OverviewData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/overview").then(r => r.json()).then(d => { setData(d); setLoading(false); });
  }, []);

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="text-sm text-gray-400 animate-pulse">Loading entity graph…</div>
    </div>
  );
  if (!data) return null;

  const gapChartData = Object.entries(data.gaps.by_type).map(([type, count]) => ({
    name: type.replace(/_/g, " "),
    count,
  }));

  const severityColor = (s: string) =>
    s === "critical" ? "bg-red-100 text-red-700" : s === "warning" ? "bg-amber-100 text-amber-700" : "bg-gray-100 text-gray-600";

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Entity overview</h1>
        <p className="text-sm text-gray-500 mt-1">
          Phase 1 — ERP-style data model with automated gap detection across orders, shipments, and inventory nodes.
        </p>
      </div>

      {/* Entity counts */}
      <div className="grid grid-cols-5 gap-3">
        {[
          { label: "Suppliers",    value: data.entities.suppliers },
          { label: "Inventory nodes", value: data.entities.nodes },
          { label: "Purchase orders", value: data.entities.orders },
          { label: "Shipments",    value: data.entities.shipments },
          { label: "Demand signals", value: data.entities.signals },
        ].map(({ label, value }) => (
          <div key={label} className="bg-white border border-gray-100 rounded-xl p-4">
            <div className="text-2xl font-semibold text-gray-900">{value}</div>
            <div className="text-xs text-gray-500 mt-1">{label}</div>
          </div>
        ))}
      </div>

      {/* Inventory snapshot */}
      <div>
        <h2 className="text-sm font-medium text-gray-700 mb-3">Inventory nodes</h2>
        <div className="grid grid-cols-3 gap-4">
          {data.nodes.map(node => {
            const pct = Math.round((node.current_stock / node.capacity) * 100);
            const atRisk = node.current_stock <= node.safety_stock * 1.5;
            return (
              <div key={node.node_id} className="bg-white border border-gray-100 rounded-xl p-5">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <div className="font-medium text-gray-900 text-sm">{node.name}</div>
                    <div className="text-xs text-gray-400 mt-0.5">{node.node_id}</div>
                  </div>
                  {atRisk && (
                    <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full font-medium">At risk</span>
                  )}
                </div>
                <div className="flex items-baseline gap-1 mb-2">
                  <span className="text-xl font-semibold text-gray-900">{node.current_stock.toLocaleString()}</span>
                  <span className="text-xs text-gray-400">/ {node.capacity.toLocaleString()} units</span>
                </div>
                <div className="w-full bg-gray-100 rounded-full h-1.5 mb-2">
                  <div
                    className={`h-1.5 rounded-full ${pct < 20 ? "bg-red-400" : pct < 40 ? "bg-amber-400" : "bg-green-400"}`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <div className="flex justify-between text-xs text-gray-400">
                  <span>{pct}% capacity</span>
                  <span>Safety stock: {node.safety_stock}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Gap summary */}
      <div className="grid grid-cols-2 gap-6">
        <div className="bg-white border border-gray-100 rounded-xl p-5">
          <h2 className="text-sm font-medium text-gray-700 mb-4">Data gaps by type</h2>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={gapChartData} layout="vertical">
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={160} />
              <Tooltip />
              <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                {gapChartData.map((entry, i) => (
                  <Cell key={i} fill={entry.count >= 3 ? "#ef4444" : "#f59e0b"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white border border-gray-100 rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-medium text-gray-700">Critical gaps</h2>
            <div className="flex gap-2 text-xs">
              <span className="bg-red-100 text-red-700 px-2 py-0.5 rounded-full">{data.gaps.critical} critical</span>
              <span className="bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full">{data.gaps.warning} warning</span>
            </div>
          </div>
          <div className="space-y-2 max-h-48 overflow-y-auto">
            {data.gaps.gaps.filter(g => g.severity === "critical").map(gap => (
              <div key={gap.gap_id} className="border border-gray-100 rounded-lg p-3">
                <div className="flex items-center gap-2 mb-1">
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${severityColor(gap.severity)}`}>
                    {gap.gap_type.replace(/_/g, " ")}
                  </span>
                  <span className="text-xs text-gray-400">{gap.entity_id}</span>
                </div>
                <p className="text-xs text-gray-600 leading-relaxed">{gap.description}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
