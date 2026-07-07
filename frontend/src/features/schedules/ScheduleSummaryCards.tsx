import { CalendarClock, CheckCircle2, Clock, PauseCircle, XCircle } from "lucide-react";

import { MetricCard } from "@/components/ui";
import { MetricCardSkeleton } from "@/components/ui/LoadingSkeleton";
import type { ScheduleSummary } from "@/features/schedules/types";

export function ScheduleSummaryCards({ summary, loading }: { summary?: ScheduleSummary; loading?: boolean }) {
  if (loading) {
    return (
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        {Array.from({ length: 5 }).map((_, i) => <MetricCardSkeleton key={i} />)}
      </div>
    );
  }
  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
      <MetricCard label="Total" value={summary?.total ?? 0} icon={<CalendarClock size={20} />} accent />
      <MetricCard label="Ativos" value={summary?.active ?? 0} icon={<CheckCircle2 size={20} />} tone="success" />
      <MetricCard label="Inativos" value={summary?.inactive ?? 0} icon={<PauseCircle size={20} />} />
      <MetricCard label="Próximas hoje" value={summary?.next_runs_today ?? 0} icon={<Clock size={20} />} accent />
      <MetricCard label="Com erro" value={summary?.last_error ?? 0} icon={<XCircle size={20} />} tone="danger" />
    </div>
  );
}
