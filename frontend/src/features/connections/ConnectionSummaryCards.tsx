import { CheckCircle2, Database, Plug, XCircle } from "lucide-react";

import { MetricCard } from "@/components/ui";
import { MetricCardSkeleton } from "@/components/ui/LoadingSkeleton";
import type { ConnectionSummary } from "@/features/connections/types";

export function ConnectionSummaryCards({
  summary,
  loading,
}: {
  summary?: ConnectionSummary;
  loading?: boolean;
}) {
  if (loading) {
    return (
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        {Array.from({ length: 5 }).map((_, i) => (
          <MetricCardSkeleton key={i} />
        ))}
      </div>
    );
  }
  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
      <MetricCard label="Total" value={summary?.total ?? 0} icon={<Plug size={20} />} accent />
      <MetricCard label="PostgreSQL" value={summary?.postgres ?? 0} icon={<Database size={20} />} />
      <MetricCard label="MySQL" value={summary?.mysql ?? 0} icon={<Database size={20} />} />
      <MetricCard label="Teste OK" value={summary?.test_success ?? 0} icon={<CheckCircle2 size={20} />} tone="success" />
      <MetricCard label="Com falha" value={summary?.test_failed ?? 0} icon={<XCircle size={20} />} tone="danger" />
    </div>
  );
}
