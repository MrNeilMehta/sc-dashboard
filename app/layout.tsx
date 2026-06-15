import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Supply Chain Decision Simulation",
  description: "ERP-style inventory simulation with LP optimization",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-gray-50 min-h-screen font-sans antialiased">
        <nav className="bg-white border-b border-gray-200 px-6 py-3 flex items-center gap-8 sticky top-0 z-10">
          <span className="font-semibold text-gray-900 text-sm tracking-tight">
            SupplyChain<span className="text-blue-600">OS</span>
          </span>
          <div className="flex gap-6 text-sm">
            <a href="/"          className="text-gray-600 hover:text-gray-900 transition-colors">Overview</a>
            <a href="/simulate"  className="text-gray-600 hover:text-gray-900 transition-colors">Simulation</a>
            <a href="/optimize"  className="text-gray-600 hover:text-gray-900 transition-colors">Optimizer</a>
          </div>
          <span className="ml-auto text-xs text-gray-400">3 nodes · 5 suppliers · 30-day horizon</span>
        </nav>
        <main className="max-w-6xl mx-auto px-6 py-8">{children}</main>
      </body>
    </html>
  );
}
