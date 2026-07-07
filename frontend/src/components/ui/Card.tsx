import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

export function Card({
  children,
  className,
  hover = false,
}: {
  children: ReactNode;
  className?: string;
  hover?: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-2xl border border-gray-200 bg-white shadow-card",
        hover && "transition-shadow hover:shadow-card-hover",
        className
      )}
    >
      {children}
    </div>
  );
}

interface MetricCardProps {
  label: string;
  value: ReactNode;
  icon?: ReactNode;
  hint?: string;
  /** Highlight the metric in brand orange (for executive/attention cards). */
  accent?: boolean;
  tone?: "default" | "danger" | "success";
  loading?: boolean;
}

export function MetricCard({ label, value, icon, hint, accent, tone = "default", loading }: MetricCardProps) {
  const iconWrap = accent
    ? "bg-brand-50 text-brand-600"
    : tone === "danger"
      ? "bg-red-50 text-red-600"
      : tone === "success"
        ? "bg-emerald-50 text-emerald-600"
        : "bg-gray-100 text-gray-500";

  return (
    <Card hover className="p-5">
      <div className="flex items-start justify-between">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">{label}</p>
          {loading ? (
            <div className="mt-2 h-8 w-16 animate-pulse rounded-md bg-gray-100" />
          ) : (
            <p className={cn("mt-1 text-3xl font-bold tabular-nums", accent ? "text-brand-600" : "text-gray-900")}>
              {value}
            </p>
          )}
          {hint && <p className="mt-1 text-xs text-gray-400">{hint}</p>}
        </div>
        {icon && (
          <div className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-xl", iconWrap)}>
            {icon}
          </div>
        )}
      </div>
    </Card>
  );
}
