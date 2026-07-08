import { Database, CheckCircle2, PauseCircle, Repeat, XCircle } from "lucide-react";

import { MetricCard } from "@/components/ui";
import { MetricCardSkeleton } from "@/components/ui/LoadingSkeleton";
import type { IngestionControlSummary } from "@/features/ingestion-control/types";

export function IngestionControlSummaryCards({ summary, loading }: { summary?: IngestionControlSummary; loading?: boolean }) {
  if (loading) {
    return (
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        {Array.from({ length: 5 }).map((_, i) => <MetricCardSkeleton key={i} />)}
      </div>
    );
  }
  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
      <MetricCard label="Tabelas" value={summary?.total ?? 0} icon={<Database size={20} />} accent />
      <MetricCard label="Ativas" value={summary?.ativas ?? 0} icon={<CheckCircle2 size={20} />} tone="success" />
      <MetricCard label="Inativas" value={summary?.inativas ?? 0} icon={<PauseCircle size={20} />} />
      <MetricCard label="Incrementais" value={summary?.incrementais ?? 0} icon={<Repeat size={20} />} accent />
      <MetricCard label="Com erro" value={summary?.ultimas_com_erro ?? 0} icon={<XCircle size={20} />} tone="danger" />
    </div>
  );
}
