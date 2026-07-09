import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Search, ShieldCheck, X } from "lucide-react";

import { api, type Page } from "@/lib/api";
import { Card, EmptyState, PageHeader } from "@/components/ui";
import { cn } from "@/lib/cn";
import { AuditEventDetailModal, type AuditEvent } from "@/features/audit/AuditEventDetailModal";

interface Summary { total: number; today: number; last_7d: number; distinct_users_7d: number; top_actions: { action: string; count: number }[] }

function fmt(t: string): string { return new Date(t).toLocaleString("pt-BR"); }

function actionTone(a: string): string {
  if (/DELETE|FAILED|BLOCKED|REMOVED/i.test(a)) return "text-red-600";
  if (/CREATED|SUCCEEDED|ACTIVATED|ADDED/i.test(a)) return "text-emerald-600";
  if (/UPDATED|RESET|REQUESTED|STARTED|RENAMED/i.test(a)) return "text-amber-600";
  return "text-gray-700";
}

const selCls = "h-9 rounded-lg border border-gray-200 bg-white px-2.5 text-sm text-gray-700 outline-none focus:border-brand-500";

export default function AuditPage() {
  const [page, setPage] = useState(1);
  const [action, setAction] = useState("");
  const [entityType, setEntityType] = useState("");
  const [user, setUser] = useState("");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<AuditEvent | null>(null);

  const query = useMemo(() => {
    const p = new URLSearchParams({ page: String(page), page_size: "30" });
    if (action) p.set("action", action);
    if (entityType) p.set("entity_type", entityType);
    if (user) p.set("user_email", user);
    if (search) p.set("search", search);
    return p.toString();
  }, [page, action, entityType, user, search]);

  const { data, isLoading } = useQuery({ queryKey: ["audit-events", query], queryFn: () => api.get<Page<AuditEvent>>(`/api/v1/audit/events?${query}`), placeholderData: (p) => p });
  const { data: summary } = useQuery({ queryKey: ["audit-summary"], queryFn: () => api.get<Summary>("/api/v1/audit/summary") });
  const { data: actions } = useQuery({ queryKey: ["audit-actions"], queryFn: () => api.get<string[]>("/api/v1/audit/actions") });

  const rows = data?.items ?? [];
  const totalPages = data?.total_pages ?? 1;
  const entityTypes = ["job", "pipeline", "connection", "variable", "cluster", "runtime", "alert_channel", "ingestion_control", "backfill", "schedule"];
  const hasFilters = !!(action || entityType || user || search);

  function clear() { setAction(""); setEntityType(""); setUser(""); setSearch(""); setPage(1); }

  return (
    <div>
      <PageHeader icon={<ShieldCheck size={22} />} title="Auditoria" description="Trilha de auditoria de todas as ações críticas da plataforma (governança)." />

      <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Card className="p-4"><p className="text-xs uppercase tracking-wide text-gray-400">Total de eventos</p><p className="mt-1.5 text-2xl font-bold text-gray-900">{summary?.total ?? "—"}</p></Card>
        <Card className="p-4"><p className="text-xs uppercase tracking-wide text-gray-400">Hoje</p><p className="mt-1.5 text-2xl font-bold text-gray-900">{summary?.today ?? "—"}</p></Card>
        <Card className="p-4"><p className="text-xs uppercase tracking-wide text-gray-400">Últimos 7 dias</p><p className="mt-1.5 text-2xl font-bold text-gray-900">{summary?.last_7d ?? "—"}</p></Card>
        <Card className="p-4"><p className="text-xs uppercase tracking-wide text-gray-400">Usuários (7d)</p><p className="mt-1.5 text-2xl font-bold text-gray-900">{summary?.distinct_users_7d ?? "—"}</p></Card>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="relative min-w-[200px] flex-1 max-w-sm">
          <Search size={15} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" />
          <input value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} placeholder="Buscar ação, usuário, detalhe…" className="h-9 w-full rounded-lg border border-gray-200 bg-white pl-8 pr-3 text-sm outline-none focus:border-brand-500" />
        </div>
        <select className={selCls} value={action} onChange={(e) => { setAction(e.target.value); setPage(1); }}>
          <option value="">Todas as ações</option>
          {(actions ?? []).map((a) => <option key={a} value={a}>{a}</option>)}
        </select>
        <select className={selCls} value={entityType} onChange={(e) => { setEntityType(e.target.value); setPage(1); }}>
          <option value="">Todas as entidades</option>
          {entityTypes.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <input className={cn(selCls, "w-40")} value={user} onChange={(e) => { setUser(e.target.value); setPage(1); }} placeholder="usuário…" />
        {hasFilters && <button onClick={clear} className="inline-flex h-9 items-center gap-1 rounded-lg px-2.5 text-sm text-gray-500 hover:bg-gray-100"><X size={14} /> Limpar</button>}
      </div>

      <Card className="overflow-hidden p-0">
        {isLoading ? (
          <div className="p-6 text-sm text-gray-400">Carregando…</div>
        ) : rows.length === 0 ? (
          <EmptyState icon={<ShieldCheck size={22} />} title="Nenhum evento" description={hasFilters ? "Nenhum evento com os filtros atuais." : "As ações críticas aparecerão aqui."} />
        ) : (
          <table className="min-w-full text-sm">
            <thead><tr className="border-b border-gray-100 bg-gray-50/70 text-xs uppercase text-gray-500">
              <th className="px-5 py-2.5 text-left">Quando</th><th className="px-5 py-2.5 text-left">Ação</th>
              <th className="px-5 py-2.5 text-left">Entidade</th><th className="px-5 py-2.5 text-left">Usuário</th>
              <th className="px-5 py-2.5 text-right">Detalhe</th>
            </tr></thead>
            <tbody>
              {rows.map((e) => (
                <tr
                  key={e.id}
                  onClick={() => setSelected(e)}
                  className="cursor-pointer border-b border-gray-50 transition-colors last:border-0 hover:bg-gray-50/70"
                >
                  <td className="px-5 py-2.5 text-xs text-gray-500">{fmt(e.created_at)}</td>
                  <td className="px-5 py-2.5"><span className={cn("font-mono text-xs font-medium", actionTone(e.action))}>{e.action}</span></td>
                  <td className="px-5 py-2.5 text-xs text-gray-600">{e.entity_type ?? "—"}{e.entity_id ? ` #${e.entity_id}` : ""}</td>
                  <td className="px-5 py-2.5 text-xs text-gray-600">{e.user_email ?? "—"}</td>
                  <td className="px-5 py-2.5 text-right">
                    <button
                      onClick={(ev) => { ev.stopPropagation(); setSelected(e); }}
                      className="text-xs font-medium text-brand-600 hover:text-brand-700"
                    >
                      Ver detalhes
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {totalPages > 1 && (
        <div className="mt-5 flex items-center justify-center gap-3">
          <button disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))} className="inline-flex h-8 items-center gap-1 rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-600 disabled:opacity-40"><ChevronLeft size={15} /> Anterior</button>
          <span className="text-sm text-gray-500">Página {page} de {totalPages}</span>
          <button disabled={page >= totalPages} onClick={() => setPage((p) => Math.min(totalPages, p + 1))} className="inline-flex h-8 items-center gap-1 rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-600 disabled:opacity-40">Próxima <ChevronRight size={15} /></button>
        </div>
      )}

      <AuditEventDetailModal eventId={selected?.id ?? null} seed={selected ?? undefined} onClose={() => setSelected(null)} />
    </div>
  );
}
