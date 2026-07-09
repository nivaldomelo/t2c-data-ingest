import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  Boxes, ChevronLeft, ChevronRight, LayoutGrid, Plus, Search, Table2, X,
} from "lucide-react";

import { api, type Page } from "@/lib/api";
import { Card, DataTable, EmptyState, PageHeader, PrimaryButton, SecondaryButton, StatusBadge } from "@/components/ui";
import type { Column } from "@/components/ui";
import { TagBadges } from "@/components/ui/TagBadges";
import { TagInput } from "@/features/tags/TagInput";
import { cn } from "@/lib/cn";
import { useAuth } from "@/lib/auth";
import { CreateJobModal } from "@/features/jobs/CreateJobModal";
import { JobDeleteDialog } from "@/features/jobs/JobDeleteDialog";
import { JobCodeWorkspaceModal } from "@/features/jobs/JobCodeWorkspaceModal";
import { JobCard, JobEngineIcon, type JobCardData } from "@/features/jobs/JobCard";

interface JobsSummary {
  total_jobs: number; spark_jobs: number; python_jobs: number; active_jobs: number; recent_failures: number;
}

const PAGE_SIZES = [12, 24, 48, 96];
const SORTS: { value: string; label: string; order: "asc" | "desc" }[] = [
  { value: "name", label: "Nome A–Z", order: "asc" },
  { value: "created_at", label: "Mais recentes", order: "desc" },
  { value: "updated_at", label: "Atualizados recentemente", order: "desc" },
  { value: "last_execution_at", label: "Última execução", order: "desc" },
  { value: "execution_count", label: "Mais executados", order: "desc" },
];
const ENGINES = [{ v: "", l: "Todas engines" }, { v: "spark_cluster", l: "Spark" }, { v: "python_worker", l: "Python" }];
const TYPES = [{ v: "", l: "Todos os tipos" }, { v: "spark_python", l: "Spark · Python" }, { v: "spark_sql", l: "Spark · SQL" }, { v: "spark_submit", l: "Spark · Submit" }, { v: "python", l: "Python" }];
const STATUSES = [{ v: "", l: "Ativos e inativos" }, { v: "true", l: "Ativos" }, { v: "false", l: "Inativos" }];
const LAST = [{ v: "", l: "Qualquer resultado" }, { v: "success", l: "Último sucesso" }, { v: "failed", l: "Última falha" }, { v: "running", l: "Em execução" }, { v: "queued", l: "Na fila" }];

const selCls = "h-9 rounded-lg border border-gray-200 bg-white px-2.5 text-sm text-gray-700 outline-none focus:border-brand-500";

export default function JobsPage() {
  const { can } = useAuth();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const canCreate = can("ingest:jobs:create");
  const canRun = can("ingest:run");
  const canEdit = can("ingest:write");
  const canDelete = can("ingest:jobs:delete");
  const canCode = can("ingest:jobs:code:read");

  const [view, setView] = useState<"cards" | "table">("cards");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(24);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [engine, setEngine] = useState("");
  const [type, setType] = useState("");
  const [activeF, setActiveF] = useState("");
  const [lastStatus, setLastStatus] = useState("");
  const [tagFilter, setTagFilter] = useState<string[]>([]);
  const [sort, setSort] = useState(SORTS[0]);

  const [createOpen, setCreateOpen] = useState(false);
  const [codeJob, setCodeJob] = useState<{ id: number; name: string } | null>(null);
  const [deleteJob, setDeleteJob] = useState<{ id: number; name: string } | null>(null);

  // Debounce the free-text search.
  useEffect(() => {
    const t = setTimeout(() => { setSearch(searchInput.trim()); setPage(1); }, 350);
    return () => clearTimeout(t);
  }, [searchInput]);
  // Reset to page 1 whenever a filter changes.
  useEffect(() => { setPage(1); }, [engine, type, activeF, lastStatus, tagFilter, pageSize, sort]);

  const query = useMemo(() => {
    const p = new URLSearchParams({ page: String(page), page_size: String(pageSize), sort_by: sort.value, sort_order: sort.order });
    if (search) p.set("search", search);
    if (engine) p.set("engine", engine);
    if (type) p.set("job_type", type);
    if (activeF) p.set("active", activeF);
    if (lastStatus) p.set("last_status", lastStatus);
    if (tagFilter.length) p.set("tags", tagFilter.join(","));
    return p.toString();
  }, [page, pageSize, sort, search, engine, type, activeF, lastStatus, tagFilter]);

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["jobs", query],
    queryFn: () => api.get<Page<JobCardData>>(`/api/v1/jobs?${query}`),
    placeholderData: (prev) => prev,
  });
  const { data: summary } = useQuery({
    queryKey: ["jobs-summary"],
    queryFn: () => api.get<JobsSummary>("/api/v1/jobs/summary"),
  });

  const run = useMutation({
    mutationFn: (jobId: number) => api.post(`/api/v1/jobs/${jobId}/run`, {}),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["jobs"] }); qc.invalidateQueries({ queryKey: ["executions"] }); },
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = data?.total_pages ?? 1;
  const hasFilters = !!(search || engine || type || activeF || lastStatus || tagFilter.length);
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);

  function clearFilters() {
    setSearchInput(""); setSearch(""); setEngine(""); setType(""); setActiveF(""); setLastStatus(""); setTagFilter([]);
  }

  const tableColumns: Column<JobCardData>[] = [
    { key: "name", header: "Job", render: (j) => (
      <div className="flex items-center gap-2">
        <JobEngineIcon kind={j.engine_kind} />
        <div>
          <button onClick={(e) => { e.stopPropagation(); navigate(`/jobs/${j.id}`); }} className="font-medium text-gray-900 hover:text-brand-600">{j.name}</button>
          <div className="font-mono text-xs text-gray-400">{j.job_type_label}</div>
        </div>
      </div>
    ) },
    { key: "tags", header: "Tags", render: (j) => <TagBadges tags={j.tags} /> },
    { key: "last", header: "Última execução", render: (j) => j.last_execution ? <StatusBadge status={j.last_execution.status} /> : <span className="text-xs text-gray-400">—</span> },
    { key: "status", header: "Status", render: (j) => <StatusBadge status={j.is_active ? "active" : "inactive"} /> },
  ];

  return (
    <div>
      <PageHeader
        icon={<Boxes size={22} />}
        title="Jobs"
        description="Gerencie jobs Spark e Python usados em execuções, pipelines e agendamentos."
        actions={canCreate && <PrimaryButton icon={<Plus size={16} />} onClick={() => setCreateOpen(true)}>Novo Job</PrimaryButton>}
      />

      {/* summary */}
      <div className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
        <SummaryCard label="Total de jobs" value={summary?.total_jobs} />
        <SummaryCard label="Spark" value={summary?.spark_jobs} accent="brand" />
        <SummaryCard label="Python" value={summary?.python_jobs} accent="sky" />
        <SummaryCard label="Ativos" value={summary?.active_jobs} accent="emerald" />
        <SummaryCard label="Falhas recentes" value={summary?.recent_failures} accent={summary?.recent_failures ? "red" : undefined} />
      </div>

      {/* filters */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="relative min-w-[220px] flex-1 max-w-sm">
          <Search size={15} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" />
          <input value={searchInput} onChange={(e) => setSearchInput(e.target.value)} placeholder="Buscar por nome, descrição, tag, conexão…"
            className="h-9 w-full rounded-lg border border-gray-200 bg-white pl-8 pr-3 text-sm outline-none focus:border-brand-500" />
        </div>
        <select className={selCls} value={engine} onChange={(e) => setEngine(e.target.value)}>{ENGINES.map((o) => <option key={o.v} value={o.v}>{o.l}</option>)}</select>
        <select className={selCls} value={type} onChange={(e) => setType(e.target.value)}>{TYPES.map((o) => <option key={o.v} value={o.v}>{o.l}</option>)}</select>
        <select className={selCls} value={activeF} onChange={(e) => setActiveF(e.target.value)}>{STATUSES.map((o) => <option key={o.v} value={o.v}>{o.l}</option>)}</select>
        <select className={selCls} value={lastStatus} onChange={(e) => setLastStatus(e.target.value)}>{LAST.map((o) => <option key={o.v} value={o.v}>{o.l}</option>)}</select>
        <div className="min-w-[180px]"><TagInput value={tagFilter} onChange={setTagFilter} allowCreate={false} placeholder="tags…" /></div>
        {hasFilters && <button onClick={clearFilters} className="inline-flex h-9 items-center gap-1 rounded-lg px-2.5 text-sm text-gray-500 hover:bg-gray-100"><X size={14} /> Limpar</button>}
      </div>

      {/* toolbar: count + sort + view */}
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2 text-sm text-gray-500">
        <span>{total > 0 ? `Mostrando ${from}–${to} de ${total} jobs` : "Nenhum job"}{isFetching && " · atualizando…"}</span>
        <div className="flex items-center gap-2">
          <select className={selCls} value={sort.value} onChange={(e) => setSort(SORTS.find((s) => s.value === e.target.value) ?? SORTS[0])}>
            {SORTS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
          <select className={selCls} value={pageSize} onChange={(e) => setPageSize(Number(e.target.value))}>
            {PAGE_SIZES.map((n) => <option key={n} value={n}>{n}/página</option>)}
          </select>
          <div className="flex overflow-hidden rounded-lg border border-gray-200">
            <button onClick={() => setView("cards")} className={cn("flex h-9 w-9 items-center justify-center", view === "cards" ? "bg-brand-500 text-white" : "bg-white text-gray-500 hover:bg-gray-50")} title="Cards"><LayoutGrid size={16} /></button>
            <button onClick={() => setView("table")} className={cn("flex h-9 w-9 items-center justify-center", view === "table" ? "bg-brand-500 text-white" : "bg-white text-gray-500 hover:bg-gray-50")} title="Tabela"><Table2 size={16} /></button>
          </div>
        </div>
      </div>

      {/* content */}
      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => <div key={i} className="h-56 animate-pulse rounded-2xl bg-gray-100" />)}
        </div>
      ) : items.length === 0 ? (
        <Card className="py-4">
          <EmptyState
            icon={<Boxes size={24} />}
            title={hasFilters ? "Nenhum job encontrado" : "Nenhum job cadastrado"}
            description={hasFilters ? "Nenhum job corresponde aos filtros atuais. Tente remover filtros ou buscar por outro termo." : "Crie seu primeiro job Spark ou Python para começar a executar ingestões."}
            action={hasFilters ? <SecondaryButton onClick={clearFilters}>Limpar filtros</SecondaryButton> : (canCreate ? <PrimaryButton icon={<Plus size={16} />} onClick={() => setCreateOpen(true)}>Novo Job</PrimaryButton> : undefined)}
          />
        </Card>
      ) : view === "cards" ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
          {items.map((j) => (
            <JobCard
              key={j.id} job={j}
              canRun={canRun} canEdit={canEdit} canDelete={canDelete} canCode={canCode}
              running={run.isPending && run.variables === j.id}
              onOpen={() => navigate(`/jobs/${j.id}`)}
              onRun={() => run.mutate(j.id)}
              onCode={() => setCodeJob({ id: j.id, name: j.name })}
              onEdit={() => navigate(`/jobs/${j.id}`, { state: { openEdit: true } })}
              onDelete={() => setDeleteJob({ id: j.id, name: j.name })}
            />
          ))}
        </div>
      ) : (
        <DataTable columns={tableColumns} rows={items} rowKey={(j) => j.id} onRowClick={(j) => navigate(`/jobs/${j.id}`)} />
      )}

      {/* pagination */}
      {totalPages > 1 && (
        <div className="mt-5 flex items-center justify-center gap-3">
          <SecondaryButton size="sm" icon={<ChevronLeft size={15} />} disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>Anterior</SecondaryButton>
          <span className="text-sm text-gray-500">Página {page} de {totalPages}</span>
          <SecondaryButton size="sm" disabled={page >= totalPages} onClick={() => setPage((p) => Math.min(totalPages, p + 1))}>Próxima <ChevronRight size={15} /></SecondaryButton>
        </div>
      )}

      <CreateJobModal open={createOpen} onClose={() => setCreateOpen(false)} canRun={canRun} />
      {codeJob && <JobCodeWorkspaceModal jobId={codeJob.id} jobName={codeJob.name} open onClose={() => setCodeJob(null)} />}
      {deleteJob && (
        <JobDeleteDialog job={deleteJob} open onClose={() => setDeleteJob(null)}
          onDeleted={() => { setDeleteJob(null); qc.invalidateQueries({ queryKey: ["jobs"] }); qc.invalidateQueries({ queryKey: ["jobs-summary"] }); }} />
      )}
    </div>
  );
}

function SummaryCard({ label, value, accent }: { label: string; value: number | undefined; accent?: "brand" | "sky" | "emerald" | "red" }) {
  const tone = accent === "brand" ? "text-brand-600" : accent === "sky" ? "text-sky-600" : accent === "emerald" ? "text-emerald-600" : accent === "red" ? "text-red-600" : "text-gray-900";
  return (
    <Card className="p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-gray-400">{label}</p>
      <p className={cn("mt-1.5 text-2xl font-bold", tone)}>{value ?? "—"}</p>
    </Card>
  );
}
