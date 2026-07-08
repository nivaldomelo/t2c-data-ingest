import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { Page } from "@/lib/api";
import { DataTable, EmptyState, StatusBadge } from "@/components/ui";
import type { Column } from "@/components/ui";
import { Modal } from "@/components/ui/Modal";
import { ExecutionTimeline } from "@/components/ui";
import type { TimelineStep } from "@/components/ui";
import { PlayCircle } from "lucide-react";
import type { PipelineExecution, StepExecution } from "@/features/pipelines/types";
import { fmtDate, fmtDuration } from "@/features/pipelines/types";

function StepsModal({ execId, onClose }: { execId: number | null; onClose: () => void }) {
  const navigate = useNavigate();
  const { data } = useQuery({
    queryKey: ["pipeline-exec-steps", execId],
    queryFn: () => api.get<StepExecution[]>(`/api/v1/pipeline-executions/${execId}/steps`),
    enabled: !!execId,
  });
  const steps: TimelineStep[] = (data ?? []).map((s) => ({
    id: s.id,
    title: `Step #${s.step_id} (job #${s.job_id})`,
    subtitle: s.message ?? undefined,
    status: s.status,
    meta: s.execution_id ? (
      <button onClick={() => navigate(`/executions/${s.execution_id}`)} className="text-xs text-brand-600 hover:underline">
        ver logs #{s.execution_id}
      </button>
    ) : undefined,
  }));
  return (
    <Modal open={!!execId} onClose={onClose} title={`Execução de pipeline #${execId}`} description="Status por step (clique para ver os logs do job)." width="max-w-2xl">
      <ExecutionTimeline steps={steps} />
    </Modal>
  );
}

export function PipelineExecutionsTab({ pipelineId }: { pipelineId: number }) {
  const [page, setPage] = useState(1);
  const [openExec, setOpenExec] = useState<number | null>(null);
  const { data, isLoading } = useQuery({
    queryKey: ["pipeline-executions", pipelineId, page],
    queryFn: () => api.get<Page<PipelineExecution>>(`/api/v1/pipelines/${pipelineId}/executions?page=${page}&page_size=25`),
    refetchInterval: 4000,
  });

  const columns: Column<PipelineExecution>[] = [
    { key: "id", header: "ID", render: (e) => <span className="font-mono text-xs text-gray-400">#{e.id}</span> },
    { key: "status", header: "Status", render: (e) => <StatusBadge status={e.status === "partial_success" ? "timeout" : e.status} label={e.status} /> },
    { key: "by", header: "Disparado por", render: (e) => <span className="text-gray-600">{e.triggered_by ?? "—"}</span> },
    { key: "start", header: "Início", render: (e) => <span className="text-gray-600">{fmtDate(e.started_at)}</span> },
    { key: "end", header: "Fim", render: (e) => <span className="text-gray-600">{fmtDate(e.finished_at)}</span> },
    { key: "dur", header: "Duração", align: "center", render: (e) => <span className="tabular-nums text-gray-600">{fmtDuration(e.duration_seconds)}</span> },
    { key: "msg", header: "Mensagem", render: (e) => <span className="block max-w-[220px] truncate text-gray-500">{e.message ?? "—"}</span> },
  ];

  return (
    <>
      <DataTable
        columns={columns}
        rows={data?.items ?? []}
        rowKey={(e) => e.id}
        loading={isLoading}
        onRowClick={(e) => setOpenExec(e.id)}
        empty={<EmptyState icon={<PlayCircle size={24} />} title="Nenhuma execução" description="Execute o pipeline para ver o histórico." />}
        pagination={data ? { page: data.page, totalPages: data.total_pages, total: data.total, hasMore: data.has_more, onPrev: () => setPage((p) => Math.max(1, p - 1)), onNext: () => setPage((p) => p + 1) } : undefined}
      />
      <StepsModal execId={openExec} onClose={() => setOpenExec(null)} />
    </>
  );
}
