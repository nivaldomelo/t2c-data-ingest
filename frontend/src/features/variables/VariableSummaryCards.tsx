import { CheckCircle2, Globe, KeyRound, Layers, Variable as VarIcon } from "lucide-react";

import { MetricCard } from "@/components/ui";
import { MetricCardSkeleton } from "@/components/ui/LoadingSkeleton";
import type { VariableSummary } from "@/features/variables/types";

export function VariableSummaryCards({ summary, loading }: { summary?: VariableSummary; loading?: boolean }) {
  if (loading) {
    return (
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        {Array.from({ length: 5 }).map((_, i) => <MetricCardSkeleton key={i} />)}
      </div>
    );
  }
  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
      <MetricCard label="Total" value={summary?.total ?? 0} icon={<VarIcon size={20} />} accent />
      <MetricCard label="Ativas" value={summary?.active ?? 0} icon={<CheckCircle2 size={20} />} tone="success" />
      <MetricCard label="Secretas" value={summary?.secret ?? 0} icon={<KeyRound size={20} />} />
      <MetricCard label="Globais" value={summary?.global_scope ?? 0} icon={<Globe size={20} />} />
      <MetricCard label="Por ambiente" value={summary?.with_environment ?? 0} icon={<Layers size={20} />} accent />
    </div>
  );
}
