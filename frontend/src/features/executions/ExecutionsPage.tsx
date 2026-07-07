import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { PlayCircle } from "lucide-react";

import { api } from "@/lib/api";
import type { Page } from "@/lib/api";
import { DataTable, EmptyState, PageHeader, StatusBadge } from "@/components/ui";
import type { Column } from "@/components/ui";

interface Execution {
  id: number;
  target_type: string;
  target_name: string | null;
  status: string;
  engine: string | null;
  triggered_by: string | null;
  started_at: string | null;
  duration_seconds: number | null;
}

const STATUSES = ["", "queued", "running", "success", "failed", "cancelled", "timeout"];
const STATUS_LABEL: Record<string, string> = {
  "": "Todos os status",
  queued: "Na fila",
  running: "Executando",
  success: "Sucesso",
  failed: "Falhou",
  cancelled: "Cancelado",
  timeout: "Timeout",
};

function fmtDur(s: number | null): string {
  if (s == null) return "—";
  if (s < 60) return `${s}s`;
  return `${Math.floor(s / 60)}m ${s % 60}s`;
}

export default function ExecutionsPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState(searchParams.get("status") ?? "");
  const [page, setPage] = useState(1);

  const { data, isLoading } = useQuery({
    queryKey: ["executions", status, page],
    queryFn: () =>
      api.get<Page<Execution>>(
        `/api/v1/executions?page=${page}&page_size=25${status ? `&status=${status}` : ""}`
      ),
  });

  const columns: Column<Execution>[] = [
    { key: "id", header: "ID", render: (e) => <span className="font-mono text-xs text-gray-400">#{e.id}</span> },
    { key: "target", header: "Alvo", render: (e) => <span className="font-medium text-gray-900">{e.target_name ?? "—"}</span> },
    {
      key: "type",
      header: "Tipo",
      render: (e) => <span className="text-gray-600 capitalize">{e.target_type}</span>,
    },
    {
      key: "engine",
      header: "Engine",
      render: (e) =>
        e.engine ? (
          <span className="inline-flex rounded-md bg-gray-100 px-2 py-0.5 font-mono text-xs text-gray-600">
            {e.engine}
          </span>
        ) : (
          "—"
        ),
    },
    { key: "user", header: "Disparado por", render: (e) => <span className="text-gray-500">{e.triggered_by ?? "—"}</span> },
    { key: "dur", header: "Duração", align: "center", render: (e) => <span className="tabular-nums text-gray-600">{fmtDur(e.duration_seconds)}</span> },
    { key: "status", header: "Status", align: "right", render: (e) => <StatusBadge status={e.status} /> },
  ];

  return (
    <div>
      <PageHeader
        icon={<PlayCircle size={22} />}
        title="Execuções"
        description="Histórico e status das execuções de jobs e pipelines."
        actions={
          <select
            value={status}
            onChange={(e) => {
              setPage(1);
              setStatus(e.target.value);
            }}
            className="h-10 rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-700 focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
          >
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {STATUS_LABEL[s]}
              </option>
            ))}
          </select>
        }
      />

      <DataTable
        columns={columns}
        rows={data?.items ?? []}
        rowKey={(e) => e.id}
        loading={isLoading}
        onRowClick={(e) => navigate(`/executions/${e.id}`)}
        empty={
          <EmptyState
            icon={<PlayCircle size={24} />}
            title="Nenhuma execução encontrada"
            description="Execute um job ou pipeline para ver o histórico aqui."
          />
        }
        pagination={
          data
            ? {
                page: data.page,
                totalPages: data.total_pages,
                total: data.total,
                hasMore: data.has_more,
                onPrev: () => setPage((p) => Math.max(1, p - 1)),
                onNext: () => setPage((p) => p + 1),
              }
            : undefined
        }
      />
    </div>
  );
}
