import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Search } from "lucide-react";

import { api } from "@/lib/api";
import type { Page } from "@/lib/api";
import { JobExecutionTable } from "@/features/jobs/JobExecutionTable";
import type { JobExecution } from "@/features/jobs/types";

const selectCls =
  "h-10 rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-700 focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-500/20";
const inputCls =
  "h-10 rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-700 focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-500/20";

const STATUSES = ["", "queued", "running", "success", "failed", "cancelled", "timeout"];
const STATUS_LABEL: Record<string, string> = {
  "": "Todos os status", queued: "Na fila", running: "Executando", success: "Sucesso",
  failed: "Falhou", cancelled: "Cancelado", timeout: "Timeout",
};

export function JobExecutionsTab({ jobId, canRun }: { jobId: number; canRun: boolean }) {
  const qc = useQueryClient();
  const [status, setStatus] = useState("");
  const [user, setUser] = useState("");
  const [search, setSearch] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(1);

  const query = useMemo(() => {
    const p = new URLSearchParams({ page: String(page), page_size: "25" });
    if (status) p.set("status", status);
    if (user.trim()) p.set("user_id", user.trim());
    if (search.trim()) p.set("search", search.trim());
    if (dateFrom) p.set("date_from", new Date(dateFrom).toISOString());
    if (dateTo) p.set("date_to", new Date(dateTo).toISOString());
    return p.toString();
  }, [jobId, status, user, search, dateFrom, dateTo, page]);

  const { data, isLoading } = useQuery({
    queryKey: ["job-executions", jobId, query],
    queryFn: () => api.get<Page<JobExecution>>(`/api/v1/jobs/${jobId}/executions?${query}`),
  });

  const rerun = useMutation({
    mutationFn: () => api.post(`/api/v1/jobs/${jobId}/run`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["job-executions", jobId] }),
  });

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="relative min-w-[200px] flex-1">
          <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            value={search}
            onChange={(e) => { setPage(1); setSearch(e.target.value); }}
            placeholder="Buscar na mensagem final…"
            className={`${inputCls} w-full pl-9`}
          />
        </div>
        <select className={selectCls} value={status} onChange={(e) => { setPage(1); setStatus(e.target.value); }}>
          {STATUSES.map((s) => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}
        </select>
        <input className={inputCls} placeholder="Usuário (e-mail)" value={user} onChange={(e) => { setPage(1); setUser(e.target.value); }} />
        <input type="date" className={selectCls} value={dateFrom} onChange={(e) => { setPage(1); setDateFrom(e.target.value); }} title="Data inicial" />
        <input type="date" className={selectCls} value={dateTo} onChange={(e) => { setPage(1); setDateTo(e.target.value); }} title="Data final" />
      </div>

      <JobExecutionTable
        rows={data?.items ?? []}
        loading={isLoading}
        canRun={canRun}
        onRerun={() => rerun.mutate()}
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
