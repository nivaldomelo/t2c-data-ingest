import { useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Code2, ListChecks, PlayCircle, Settings2 } from "lucide-react";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/cn";
import { Skeleton } from "@/components/ui/LoadingSkeleton";
import { EmptyState } from "@/components/ui";
import { JobHeader } from "@/features/jobs/JobHeader";
import { JobOverviewTab } from "@/features/jobs/JobOverviewTab";
import { JobExecutionsTab } from "@/features/jobs/JobExecutionsTab";
import { JobCodeEditor } from "@/features/jobs/JobCodeEditor";
import { JobSettingsTab } from "@/features/jobs/JobSettingsTab";
import type { JobDetail } from "@/features/jobs/types";

type TabKey = "overview" | "executions" | "code" | "settings";

const TABS: { key: TabKey; label: string; icon: typeof PlayCircle }[] = [
  { key: "overview", label: "Visão geral", icon: ListChecks },
  { key: "executions", label: "Execuções", icon: PlayCircle },
  { key: "code", label: "Código", icon: Code2 },
  { key: "settings", label: "Configurações", icon: Settings2 },
];

export default function JobDetailPage() {
  const { id } = useParams();
  const jobId = Number(id);
  const qc = useQueryClient();
  const { can } = useAuth();
  const [tab, setTab] = useState<TabKey>("overview");

  const { data: job, isLoading, error } = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => api.get<JobDetail>(`/api/v1/jobs/${jobId}`),
  });

  const run = useMutation({
    mutationFn: () => api.post(`/api/v1/jobs/${jobId}/run`, {}),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["job", jobId] });
      qc.invalidateQueries({ queryKey: ["job-executions", jobId] });
      setTab("executions");
    },
  });

  if (isLoading) {
    return (
      <div>
        <Skeleton className="h-8 w-64" />
        <Skeleton className="mt-6 h-40 rounded-2xl" />
      </div>
    );
  }
  if (error || !job) {
    return <EmptyState title="Job não encontrado" description="O job solicitado não existe ou foi removido." />;
  }

  const canRun = can("ingest:run");

  return (
    <div>
      <JobHeader job={job} canRun={canRun} running={run.isPending} onRun={() => run.mutate()} />

      {/* Abas */}
      <div className="mb-6 border-b border-gray-200">
        <nav className="-mb-px flex gap-1">
          {TABS.map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={cn(
                "inline-flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors",
                tab === key
                  ? "border-brand-500 text-brand-600"
                  : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700"
              )}
            >
              <Icon size={16} />
              {label}
            </button>
          ))}
        </nav>
      </div>

      {tab === "overview" && <JobOverviewTab job={job} />}
      {tab === "executions" && <JobExecutionsTab jobId={jobId} canRun={canRun} />}
      {tab === "code" && <JobCodeEditor jobId={jobId} />}
      {tab === "settings" && <JobSettingsTab job={job} />}
    </div>
  );
}
