import type { ReactNode } from "react";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-xl border border-slate-200 bg-white shadow-sm ${className}`}>
      {children}
    </div>
  );
}

export function StatCard({ label, value }: { label: string; value: ReactNode }) {
  return (
    <Card className="p-4">
      <div className="text-sm text-slate-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-slate-900">{value}</div>
    </Card>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    success: "bg-green-100 text-green-700",
    running: "bg-blue-100 text-blue-700",
    queued: "bg-slate-100 text-slate-600",
    failed: "bg-red-100 text-red-700",
    timeout: "bg-amber-100 text-amber-700",
    cancelled: "bg-slate-200 text-slate-600",
    skipped: "bg-slate-100 text-slate-500",
    active: "bg-green-100 text-green-700",
    inactive: "bg-slate-200 text-slate-600",
  };
  const cls = map[status] ?? "bg-slate-100 text-slate-600";
  return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}>{status}</span>;
}

export function DataTable({
  columns,
  children,
  empty = "Nenhum registro.",
  isEmpty = false,
}: {
  columns: string[];
  children: ReactNode;
  empty?: string;
  isEmpty?: boolean;
}) {
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <thead className="bg-slate-50">
          <tr>
            {columns.map((c) => (
              <th key={c} className="px-4 py-3 text-left font-medium text-slate-500">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {isEmpty ? (
            <tr>
              <td colSpan={columns.length} className="px-4 py-8 text-center text-slate-400">
                {empty}
              </td>
            </tr>
          ) : (
            children
          )}
        </tbody>
      </table>
    </div>
  );
}
