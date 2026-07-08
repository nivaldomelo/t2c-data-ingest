import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, ArrowLeft, CalendarClock, Code2, ListChecks, PlayCircle, Settings2 } from "lucide-react";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/cn";
import { Skeleton } from "@/components/ui/LoadingSkeleton";
import { Card, EmptyState, SecondaryButton } from "@/components/ui";
import { JobHeader } from "@/features/jobs/JobHeader";
import { JobOverviewTab } from "@/features/jobs/JobOverviewTab";
import { JobExecutionsTab } from "@/features/jobs/JobExecutionsTab";
import { JobSettingsTab } from "@/features/jobs/JobSettingsTab";
import { JobSchedulesTab } from "@/features/schedules/JobSchedulesTab";
import { JobCodeWorkspaceModal } from "@/features/jobs/JobCodeWorkspaceModal";
import { JobEditModal } from "@/features/jobs/JobEditModal";
import { JobDeleteDialog } from "@/features/jobs/JobDeleteDialog";
import { fmtDate } from "@/features/jobs/types";
import type { JobDetail } from "@/features/jobs/types";

type TabKey = "overview" | "executions" | "schedules" | "code" | "settings";

const TABS: { key: TabKey; label: string; icon: typeof PlayCircle }[] = [
  { key: "overview", label: "Visão geral", icon: ListChecks },
  { key: "executions", label: "Execuções", icon: PlayCircle },
  { key: "schedules", label: "Agendamentos", icon: CalendarClock },
  { key: "code", label: "Código", icon: Code2 },
  { key: "settings", label: "Configurações", icon: Settings2 },
];

export default function JobDetailPage() {
  const { id } = useParams();
  const jobId = Number(id);
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { can } = useAuth();
  const [tab, setTab] = useState<TabKey>("overview");
  const [workspaceOpen, setWorkspaceOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

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

  // Deleted job: no run/edit/code — just an archival notice.
  if (job.deleted_at) {
    return (
      <div>
        <button
          onClick={() => navigate("/jobs")}
          className="mb-4 inline-flex items-center gap-1.5 text-sm text-gray-500 transition-colors hover:text-gray-800"
        >
          <ArrowLeft size={16} /> Voltar para Jobs
        </button>
        <Card className="p-8">
          <div className="flex items-start gap-4">
            <div className="rounded-xl bg-amber-50 p-3 text-amber-600"><Archive size={24} /></div>
            <div className="min-w-0">
              <h1 className="text-xl font-bold text-gray-900">Este job foi excluído</h1>
              <p className="mt-1 text-sm text-gray-500">
                <span className="font-medium text-gray-700">{job.name}</span> foi removido da listagem ativa.
                O código foi arquivado e não pode mais ser executado ou editado.
              </p>
              <dl className="mt-5 space-y-2 text-sm">
                <div className="flex flex-col gap-0.5">
                  <dt className="text-xs font-medium uppercase tracking-wide text-gray-400">Código arquivado em</dt>
                  <dd className="break-all font-mono text-xs text-gray-700">{job.archived_code_path ?? "—"}</dd>
                </div>
                <div className="flex gap-8">
                  <div>
                    <dt className="text-xs font-medium uppercase tracking-wide text-gray-400">Data da exclusão</dt>
                    <dd className="text-gray-700">{fmtDate(job.deleted_at)}</dd>
                  </div>
                  <div>
                    <dt className="text-xs font-medium uppercase tracking-wide text-gray-400">Usuário responsável</dt>
                    <dd className="text-gray-700">{job.deleted_by ?? "—"}</dd>
                  </div>
                </div>
                {job.delete_reason && (
                  <div>
                    <dt className="text-xs font-medium uppercase tracking-wide text-gray-400">Motivo</dt>
                    <dd className="text-gray-700">{job.delete_reason}</dd>
                  </div>
                )}
              </dl>
              <div className="mt-6">
                <SecondaryButton onClick={() => navigate("/jobs")}>Voltar para a listagem</SecondaryButton>
              </div>
            </div>
          </div>
        </Card>
      </div>
    );
  }

  const canRun = can("ingest:run");
  const canEdit = can("ingest:write");
  const canDelete = can("ingest:jobs:delete");

  return (
    <div>
      <JobHeader
        job={job}
        canRun={canRun}
        canEdit={canEdit}
        canDelete={canDelete}
        running={run.isPending}
        onRun={() => run.mutate()}
        onEdit={() => setEditOpen(true)}
        onDelete={() => setDeleteOpen(true)}
      />

      {/* Abas — "Código" abre o workspace direto (sem trocar o conteúdo abaixo). */}
      <div className="mb-6 border-b border-gray-200">
        <nav className="-mb-px flex gap-1">
          {TABS.map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              onClick={() => (key === "code" ? setWorkspaceOpen(true) : setTab(key))}
              className={cn(
                "inline-flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors",
                tab === key && key !== "code"
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
      {tab === "schedules" && <JobSchedulesTab jobId={jobId} />}
      {tab === "settings" && <JobSettingsTab job={job} />}

      <JobCodeWorkspaceModal
        jobId={jobId}
        jobName={job.name}
        open={workspaceOpen}
        onClose={() => setWorkspaceOpen(false)}
      />
      {editOpen && <JobEditModal job={job} open={editOpen} onClose={() => setEditOpen(false)} />}
      {deleteOpen && (
        <JobDeleteDialog
          job={job}
          open={deleteOpen}
          onClose={() => setDeleteOpen(false)}
          onDeleted={() => {
            setDeleteOpen(false);
            qc.invalidateQueries({ queryKey: ["jobs"] });
            navigate("/jobs");
          }}
        />
      )}
    </div>
  );
}
