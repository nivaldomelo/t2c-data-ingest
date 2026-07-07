import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { Page } from "@/lib/api";
import { DataTable, StatusBadge } from "@/components/ui";
import type { Column } from "@/components/ui";
import { Modal } from "@/components/ui/Modal";
import type { Schedule, ScheduleRun } from "@/features/schedules/types";
import { fmtDateTime } from "@/features/schedules/types";

export function ScheduleRunsModal({ schedule, onClose }: { schedule: Schedule | null; onClose: () => void }) {
  const navigate = useNavigate();
  const { data, isLoading } = useQuery({
    queryKey: ["schedule-runs", schedule?.id],
    queryFn: () => api.get<Page<ScheduleRun>>(`/api/v1/job-schedules/${schedule!.id}/runs?page=1&page_size=25`),
    enabled: !!schedule,
  });

  const columns: Column<ScheduleRun>[] = [
    { key: "for", header: "Previsto", render: (r) => <span className="text-gray-700">{fmtDateTime(r.scheduled_for)}</span> },
    { key: "at", header: "Disparado", render: (r) => <span className="text-gray-600">{fmtDateTime(r.triggered_at)}</span> },
    { key: "status", header: "Status", render: (r) => <StatusBadge status={r.status === "triggered" ? "queued" : r.status} label={r.status === "triggered" ? "Disparado" : undefined} /> },
    {
      key: "exec",
      header: "Execução",
      render: (r) =>
        r.execution_id ? (
          <button onClick={() => navigate(`/executions/${r.execution_id}`)} className="font-mono text-xs text-brand-600 hover:underline">
            #{r.execution_id}
          </button>
        ) : <span className="text-gray-400">—</span>,
    },
    { key: "msg", header: "Mensagem", render: (r) => <span className="block max-w-[240px] truncate text-xs text-gray-500" title={r.message ?? ""}>{r.message ?? "—"}</span> },
  ];

  return (
    <Modal open={!!schedule} onClose={onClose} title={`Execuções — ${schedule?.name ?? ""}`} description="Disparos gerados por este agendamento." width="max-w-3xl">
      <DataTable columns={columns} rows={data?.items ?? []} rowKey={(r) => r.id} loading={isLoading} empty={<div className="p-6 text-center text-sm text-gray-400">Nenhum disparo ainda.</div>} />
    </Modal>
  );
}
