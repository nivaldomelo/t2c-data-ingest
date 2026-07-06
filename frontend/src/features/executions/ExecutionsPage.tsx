import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { Page } from "@/lib/api";
import { DataTable, StatusBadge } from "@/components/ui/Table";

interface Execution {
  id: number;
  target_type: string;
  target_name: string | null;
  status: string;
  engine: string | null;
  triggered_by: string | null;
  started_at: string | null;
  duration_seconds: number | null;
  final_message: string | null;
}

const STATUSES = ["", "queued", "running", "success", "failed", "cancelled", "timeout"];

export default function ExecutionsPage() {
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);

  const { data, isLoading } = useQuery({
    queryKey: ["executions", status, page],
    queryFn: () =>
      api.get<Page<Execution>>(
        `/api/v1/executions?page=${page}&page_size=25${status ? `&status=${status}` : ""}`
      ),
  });

  const rows = data?.items ?? [];

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Execuções</h1>
          <p className="text-sm text-slate-500">Histórico e status das execuções.</p>
        </div>
        <select
          value={status}
          onChange={(e) => {
            setPage(1);
            setStatus(e.target.value);
          }}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
        >
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s === "" ? "Todos os status" : s}
            </option>
          ))}
        </select>
      </div>

      <div className="mt-6">
        <DataTable
          columns={["ID", "Alvo", "Tipo", "Engine", "Disparado por", "Duração", "Status"]}
          isEmpty={!isLoading && rows.length === 0}
          empty="Nenhuma execução encontrada."
        >
          {rows.map((e) => (
            <tr key={e.id}>
              <td className="px-4 py-3 font-mono text-xs text-slate-500">#{e.id}</td>
              <td className="px-4 py-3 font-medium text-slate-800">{e.target_name ?? "—"}</td>
              <td className="px-4 py-3 text-slate-600">{e.target_type}</td>
              <td className="px-4 py-3 text-slate-600">{e.engine ?? "—"}</td>
              <td className="px-4 py-3 text-slate-600">{e.triggered_by ?? "—"}</td>
              <td className="px-4 py-3 text-slate-600">
                {e.duration_seconds != null ? `${e.duration_seconds}s` : "—"}
              </td>
              <td className="px-4 py-3">
                <StatusBadge status={e.status} />
              </td>
            </tr>
          ))}
        </DataTable>

        {data && data.total_pages > 1 && (
          <div className="mt-4 flex items-center justify-between text-sm text-slate-500">
            <span>
              {data.total} execuções · página {data.page}/{data.total_pages}
            </span>
            <div className="flex gap-2">
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
                className="rounded-lg border border-slate-300 px-3 py-1 disabled:opacity-40"
              >
                Anterior
              </button>
              <button
                disabled={!data.has_more}
                onClick={() => setPage((p) => p + 1)}
                className="rounded-lg border border-slate-300 px-3 py-1 disabled:opacity-40"
              >
                Próxima
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
