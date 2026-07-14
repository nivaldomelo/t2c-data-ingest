import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Cable, CheckCircle2, Clock, RefreshCw, RotateCcw, Send, Skull, XCircle,
} from "lucide-react";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { PageHeader, MetricCard, SecondaryButton, PrimaryButton, Modal, JsonViewer } from "@/components/ui";
import { MetricCardSkeleton } from "@/components/ui/LoadingSkeleton";
import { cn } from "@/lib/cn";

interface Stats {
  by_status: Record<string, number>;
  by_event_type: Record<string, number>;
  pending: number; sent: number; failed: number; dead: number;
  last_sent_at: string | null;
}
interface OutboxRow {
  id: number; event_type: string; aggregate_type: string | null; aggregate_id: string | null;
  status: string; attempts: number; max_attempts: number; error: string | null;
  created_at: string | null; last_attempt_at: string | null; next_attempt_at: string | null;
  sent_at: string | null; dead_at: string | null;
}
interface OutboxDetail extends OutboxRow { payload: unknown; idempotency_key: string | null; }
interface OutboxPage { total: number; page: number; page_size: number; items: OutboxRow[]; }

const BASE = "/api/v1/integrations/t2c-data";
const fmt = (t: string | null) => (t ? new Date(t).toLocaleString("pt-BR") : "—");

const STATUS_STYLE: Record<string, string> = {
  pending: "bg-amber-50 text-amber-700 ring-amber-600/20",
  processing: "bg-sky-50 text-sky-700 ring-sky-600/20",
  sent: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  failed: "bg-orange-50 text-orange-700 ring-orange-600/20",
  dead: "bg-red-50 text-red-700 ring-red-600/20",
};

function StatusPill({ s }: { s: string }) {
  return (
    <span className={cn("inline-flex rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ring-inset",
      STATUS_STYLE[s] ?? "bg-gray-100 text-gray-600 ring-gray-500/20")}>{s}</span>
  );
}

const STATUS_FILTERS = ["", "pending", "processing", "sent", "failed", "dead"];

export default function IntegrationsPage() {
  const qc = useQueryClient();
  const { can } = useAuth();
  const canRetry = can("ingest:integrations:retry");
  const [status, setStatus] = useState("");
  const [eventType, setEventType] = useState("");
  const [page, setPage] = useState(1);
  const [detailId, setDetailId] = useState<number | null>(null);

  const stats = useQuery({ queryKey: ["integ", "stats"], queryFn: () => api.get<Stats>(`${BASE}/stats`), refetchInterval: 30_000 });
  const list = useQuery({
    queryKey: ["integ", "outbox", status, eventType, page],
    queryFn: () => api.get<OutboxPage>(`${BASE}/outbox?page=${page}&page_size=25` +
      (status ? `&status=${status}` : "") + (eventType ? `&event_type=${encodeURIComponent(eventType)}` : "")),
    refetchInterval: 30_000,
  });
  const detail = useQuery({
    queryKey: ["integ", "detail", detailId],
    queryFn: () => api.get<OutboxDetail>(`${BASE}/outbox/${detailId}`),
    enabled: detailId != null,
  });

  function refresh() { qc.invalidateQueries({ queryKey: ["integ"] }); }

  const retryOne = useMutation({
    mutationFn: (id: number) => api.post(`${BASE}/outbox/${id}/retry`, {}),
    onSuccess: refresh,
  });
  const retryDead = useMutation({
    mutationFn: () => api.post<{ requeued: number }>(`${BASE}/outbox/retry-dead`, {}),
    onSuccess: refresh,
  });

  const s = stats.data;
  const cards = useMemo(() => ([
    { label: "Pendentes", v: s?.pending ?? 0, icon: <Clock size={20} />, tone: undefined },
    { label: "Enviados", v: s?.sent ?? 0, icon: <CheckCircle2 size={20} />, tone: "success" as const },
    { label: "Com erro", v: s?.failed ?? 0, icon: <XCircle size={20} />, tone: (s?.failed ? "danger" : undefined) as any },
    { label: "Dead-letter", v: s?.dead ?? 0, icon: <Skull size={20} />, tone: (s?.dead ? "danger" : undefined) as any },
  ]), [s]);

  const eventTypes = Object.keys(s?.by_event_type ?? {}).sort();
  const items = list.data?.items ?? [];
  const total = list.data?.total ?? 0;
  const pageSize = list.data?.page_size ?? 25;
  const maxPage = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div>
      <PageHeader
        icon={<Cable size={22} />}
        title="Integração com o t2c_data"
        description="Eventos operacionais (linhagem, qualidade, schema, Data Lake, incidentes) entregues ao t2c_data via outbox transacional com retry e idempotência."
        actions={
          <div className="flex items-center gap-2">
            {canRetry && (
              <SecondaryButton icon={<RotateCcw size={16} />} onClick={() => retryDead.mutate()}
                disabled={retryDead.isPending || !(s?.dead)}>
                Reprocessar dead ({s?.dead ?? 0})
              </SecondaryButton>
            )}
            <SecondaryButton icon={<RefreshCw size={16} />} onClick={refresh}>Atualizar</SecondaryButton>
          </div>
        }
      />

      {stats.isLoading ? (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">{Array.from({ length: 4 }).map((_, i) => <MetricCardSkeleton key={i} />)}</div>
      ) : (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {cards.map((c) => <MetricCard key={c.label} label={c.label} value={c.v} icon={c.icon} tone={c.tone} />)}
        </div>
      )}

      {s?.last_sent_at && (
        <p className="mt-3 flex items-center gap-1.5 text-xs text-gray-400"><Send size={13} /> Último envio: {fmt(s.last_sent_at)}</p>
      )}

      {/* Filtros */}
      <div className="mt-6 flex flex-wrap items-center gap-2">
        {STATUS_FILTERS.map((f) => (
          <button key={f || "all"} onClick={() => { setStatus(f); setPage(1); }}
            className={cn("rounded-lg px-3 py-1.5 text-xs font-medium transition-colors",
              status === f ? "bg-brand-500 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200")}>
            {f || "Todos"}
          </button>
        ))}
        <select value={eventType} onChange={(e) => { setEventType(e.target.value); setPage(1); }}
          className="ml-auto rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-xs text-gray-700">
          <option value="">Todos os tipos</option>
          {eventTypes.map((t) => <option key={t} value={t}>{t} ({s?.by_event_type[t]})</option>)}
        </select>
      </div>

      {/* Tabela */}
      <div className="mt-3 overflow-hidden rounded-2xl border border-gray-100 bg-white">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-[11px] uppercase tracking-wide text-gray-400">
              <tr>
                <th className="px-3 py-2 font-medium">ID</th>
                <th className="px-3 py-2 font-medium">Tipo de evento</th>
                <th className="px-3 py-2 font-medium">Aggregate</th>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-3 py-2 font-medium">Tentativas</th>
                <th className="px-3 py-2 font-medium">Criado</th>
                <th className="px-3 py-2 font-medium">Últ. tentativa</th>
                <th className="px-3 py-2 font-medium">Erro</th>
                <th className="px-3 py-2 font-medium text-right">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {items.length === 0 && !list.isLoading && (
                <tr><td colSpan={9} className="px-3 py-10 text-center text-sm text-gray-400">Nenhum evento de integração.</td></tr>
              )}
              {items.map((r) => (
                <tr key={r.id} className="hover:bg-gray-50/60">
                  <td className="px-3 py-1.5 font-mono text-xs text-gray-500">#{r.id}</td>
                  <td className="px-3 py-1.5 font-mono text-xs">{r.event_type}</td>
                  <td className="px-3 py-1.5 text-xs text-gray-500">{r.aggregate_type ? `${r.aggregate_type}:${r.aggregate_id}` : "—"}</td>
                  <td className="px-3 py-1.5"><StatusPill s={r.status} /></td>
                  <td className="px-3 py-1.5 tabular-nums text-gray-600">{r.attempts}/{r.max_attempts}</td>
                  <td className="px-3 py-1.5 text-xs text-gray-500">{fmt(r.created_at)}</td>
                  <td className="px-3 py-1.5 text-xs text-gray-500">{fmt(r.last_attempt_at)}</td>
                  <td className="px-3 py-1.5 max-w-[220px] truncate text-xs text-red-600" title={r.error ?? ""}>{r.error ?? "—"}</td>
                  <td className="px-3 py-1.5 text-right">
                    <div className="inline-flex items-center gap-1.5">
                      <button onClick={() => setDetailId(r.id)} className="rounded px-2 py-1 text-xs font-medium text-brand-600 hover:bg-brand-50">Ver</button>
                      {canRetry && r.status !== "sent" && (
                        <button onClick={() => retryOne.mutate(r.id)} disabled={retryOne.isPending}
                          className="rounded px-2 py-1 text-xs font-medium text-gray-600 hover:bg-gray-100">Reprocessar</button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {/* Paginação */}
        <div className="flex items-center justify-between border-t border-gray-100 px-4 py-2 text-xs text-gray-500">
          <span>{total} evento(s)</span>
          <div className="flex items-center gap-2">
            <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}
              className="rounded px-2 py-1 disabled:opacity-40 enabled:hover:bg-gray-100">Anterior</button>
            <span>{page} / {maxPage}</span>
            <button disabled={page >= maxPage} onClick={() => setPage((p) => p + 1)}
              className="rounded px-2 py-1 disabled:opacity-40 enabled:hover:bg-gray-100">Próxima</button>
          </div>
        </div>
      </div>

      {/* Detalhe / payload */}
      <Modal open={detailId != null} onClose={() => setDetailId(null)} title={`Evento #${detailId ?? ""}`}>
        {detail.isLoading ? (
          <p className="text-sm text-gray-400">Carregando…</p>
        ) : detail.data ? (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3 text-sm">
              <Field label="Tipo de evento" value={detail.data.event_type} mono />
              <Field label="Status" value={<StatusPill s={detail.data.status} />} />
              <Field label="Aggregate" value={detail.data.aggregate_type ? `${detail.data.aggregate_type}:${detail.data.aggregate_id}` : "—"} />
              <Field label="Tentativas" value={`${detail.data.attempts}/${detail.data.max_attempts}`} />
              <Field label="Idempotency key" value={detail.data.idempotency_key ?? "—"} mono />
              <Field label="Próxima tentativa" value={fmt(detail.data.next_attempt_at)} />
              <Field label="Enviado" value={fmt(detail.data.sent_at)} />
              <Field label="Dead-letter" value={fmt(detail.data.dead_at)} />
            </div>
            {detail.data.error && (
              <div className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">{detail.data.error}</div>
            )}
            <JsonViewer data={detail.data.payload} label="Payload (mascarado)" />
            {canRetry && detail.data.status !== "sent" && (
              <PrimaryButton icon={<RotateCcw size={16} />}
                onClick={() => { retryOne.mutate(detail.data!.id); setDetailId(null); }}>
                Reprocessar evento
              </PrimaryButton>
            )}
          </div>
        ) : (
          <p className="text-sm text-gray-400">Não encontrado.</p>
        )}
      </Modal>
    </div>
  );
}

function Field({ label, value, mono }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wide text-gray-400">{label}</div>
      <div className={cn("mt-0.5 text-gray-800", mono && "font-mono text-xs break-all")}>{value}</div>
    </div>
  );
}
