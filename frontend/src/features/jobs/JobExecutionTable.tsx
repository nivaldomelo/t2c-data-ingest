import { useNavigate } from "react-router-dom";
import { Eye, FileText, RotateCw } from "lucide-react";

import { DataTable, EmptyState, StatusBadge } from "@/components/ui";
import type { Column } from "@/components/ui";
import { cn } from "@/lib/cn";
import { PlayCircle } from "lucide-react";
import type { JobExecution } from "@/features/jobs/types";
import { fmtDate, fmtDuration } from "@/features/jobs/types";

interface Props {
  rows: JobExecution[];
  loading?: boolean;
  canRun?: boolean;
  onRerun?: (e: JobExecution) => void;
  pagination?: {
    page: number;
    totalPages: number;
    total: number;
    hasMore: boolean;
    onPrev: () => void;
    onNext: () => void;
  };
}

function IconAction({ title, onClick, children }: { title: string; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      title={title}
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      className={cn(
        "inline-flex h-8 w-8 items-center justify-center rounded-lg text-gray-400",
        "transition-colors hover:bg-gray-100 hover:text-gray-700"
      )}
    >
      {children}
    </button>
  );
}

export function JobExecutionTable({ rows, loading, canRun, onRerun, pagination }: Props) {
  const navigate = useNavigate();

  const columns: Column<JobExecution>[] = [
    { key: "id", header: "ID", render: (e) => <span className="font-mono text-xs text-gray-400">#{e.id}</span> },
    { key: "status", header: "Status", render: (e) => <StatusBadge status={e.status} /> },
    { key: "start", header: "Início", render: (e) => <span className="text-gray-600">{fmtDate(e.started_at)}</span> },
    { key: "end", header: "Fim", render: (e) => <span className="text-gray-600">{fmtDate(e.finished_at)}</span> },
    { key: "dur", header: "Duração", align: "center", render: (e) => <span className="tabular-nums text-gray-600">{fmtDuration(e.duration_seconds)}</span> },
    { key: "user", header: "Usuário", render: (e) => <span className="text-gray-500">{e.triggered_by ?? "—"}</span> },
    {
      key: "engine",
      header: "Engine",
      render: (e) => (e.engine ? <span className="inline-flex rounded-md bg-gray-100 px-2 py-0.5 font-mono text-xs text-gray-600">{e.engine}</span> : "—"),
    },
    { key: "msg", header: "Mensagem", render: (e) => <span className="block max-w-[220px] truncate text-gray-500" title={e.final_message ?? ""}>{e.final_message ?? "—"}</span> },
    {
      key: "actions",
      header: "",
      align: "right",
      render: (e) => (
        <div className="flex items-center justify-end gap-0.5">
          <IconAction title="Ver detalhes" onClick={() => navigate(`/executions/${e.id}`)}>
            <Eye size={16} />
          </IconAction>
          <IconAction title="Ver logs" onClick={() => navigate(`/executions/${e.id}`)}>
            <FileText size={16} />
          </IconAction>
          {canRun && onRerun && (
            <IconAction title="Reexecutar" onClick={() => onRerun(e)}>
              <RotateCw size={16} />
            </IconAction>
          )}
        </div>
      ),
    },
  ];

  return (
    <DataTable
      columns={columns}
      rows={rows}
      rowKey={(e) => e.id}
      loading={loading}
      onRowClick={(e) => navigate(`/executions/${e.id}`)}
      empty={
        <EmptyState
          icon={<PlayCircle size={24} />}
          title="Nenhuma execução"
          description="Este job ainda não foi executado."
        />
      }
      pagination={pagination}
    />
  );
}
