import { Cloud, Database, Globe, Plug, XCircle } from "lucide-react";

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
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-6">
        {Array.from({ length: 6 }).map((_, i) => (
          <MetricCardSkeleton key={i} />
        ))}
      </div>
    );
  }
  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
      <MetricCard label="Total" value={summary?.total ?? 0} icon={<Plug size={20} />} accent />
      <MetricCard label="Bancos de dados" value={summary?.database ?? 0} icon={<Database size={20} />} />
      <MetricCard label="Data Lake / Storage" value={summary?.storage ?? 0} icon={<Cloud size={20} />} />
      <MetricCard label="APIs / SaaS" value={summary?.api ?? 0} icon={<Globe size={20} />} />
      <MetricCard label="Com falha" value={summary?.test_failed ?? 0} icon={<XCircle size={20} />} tone="danger" />
    </div>
  );
}
