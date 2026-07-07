import type { ReactNode } from "react";

import { cn } from "@/lib/cn";
import { TableSkeleton } from "@/components/ui/LoadingSkeleton";

export interface Column<T> {
  key: string;
  header: ReactNode;
  render: (row: T) => ReactNode;
  align?: "left" | "right" | "center";
  className?: string;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string | number;
  loading?: boolean;
  onRowClick?: (row: T) => void;
  empty?: ReactNode;
  pagination?: {
    page: number;
    totalPages: number;
    total: number;
    hasMore: boolean;
    onPrev: () => void;
    onNext: () => void;
  };
}

const alignClass = { left: "text-left", right: "text-right", center: "text-center" } as const;

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  loading,
  onRowClick,
  empty,
  pagination,
}: DataTableProps<T>) {
  return (
    <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-card">
      <div className="overflow-x-auto">
        <table className="min-w-full border-separate border-spacing-0 text-sm">
          <thead>
            <tr>
              {columns.map((c) => (
                <th
                  key={c.key}
                  className={cn(
                    "sticky top-0 z-10 border-b border-gray-200 bg-gray-50/80 px-5 py-3 text-xs font-semibold uppercase tracking-wide text-gray-500 backdrop-blur",
                    alignClass[c.align ?? "left"]
                  )}
                >
                  {c.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={columns.length} className="p-0">
                  <TableSkeleton cols={columns.length} />
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={columns.length}>{empty}</td>
              </tr>
            ) : (
              rows.map((row) => (
                <tr
                  key={rowKey(row)}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                  className={cn(
                    "group transition-colors",
                    onRowClick && "cursor-pointer hover:bg-brand-50/40"
                  )}
                >
                  {columns.map((c) => (
                    <td
                      key={c.key}
                      className={cn(
                        "border-b border-gray-100 px-5 py-3.5 text-gray-700 group-last:border-0",
                        alignClass[c.align ?? "left"],
                        c.className
                      )}
                    >
                      {c.render(row)}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {pagination && pagination.total > 0 && (
        <div className="flex items-center justify-between border-t border-gray-100 px-5 py-3 text-sm text-gray-500">
          <span>
            <span className="font-medium text-gray-700">{pagination.total}</span> registro(s) · página{" "}
            {pagination.page}/{Math.max(pagination.totalPages, 1)}
          </span>
          <div className="flex gap-2">
            <button
              disabled={pagination.page <= 1}
              onClick={pagination.onPrev}
              className="rounded-lg border border-gray-200 px-3 py-1.5 font-medium text-gray-600 transition-colors hover:bg-gray-50 disabled:opacity-40"
            >
              Anterior
            </button>
            <button
              disabled={!pagination.hasMore}
              onClick={pagination.onNext}
              className="rounded-lg border border-gray-200 px-3 py-1.5 font-medium text-gray-600 transition-colors hover:bg-gray-50 disabled:opacity-40"
            >
              Próxima
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
