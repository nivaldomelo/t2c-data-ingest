import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Boxes, Database, LineChart, Workflow } from "lucide-react";

import { api } from "@/lib/api";
import type { Page } from "@/lib/api";
import { PageHeader, MetricCard } from "@/components/ui";
import { MetricCardSkeleton } from "@/components/ui/LoadingSkeleton";
import { cn } from "@/lib/cn";

type EntityType = "control" | "job" | "pipeline";
type Row = Record<string, unknown>;
interface DayPoint {
  date: string; runs: number; success: number; failed: number;
  records_read: number; records_written: number; avg_duration: number | null;
}
interface History {
  entity: { type: string; id: number; name: string };
  window_days: number;
  summary: Record<string, number | string | null>;
  series: DayPoint[];
  executions: Row[];
}

const TYPES: { key: EntityType; label: string; icon: typeof Database }[] = [
  { key: "control", label: "Tabela (Controle)", icon: Database },
  { key: "job", label: "Job", icon: Boxes },
  { key: "pipeline", label: "Pipeline", icon: Workflow },
];
const WINDOWS = [7, 30, 90];

const fmtDate = (t: unknown) => (t ? new Date(String(t)).toLocaleString("pt-BR") : "—");
const fmtDay = (d: string) => d.slice(5); // MM-DD
const fmtDur = (s: unknown) => (s == null ? "—" : `${Math.floor(Number(s) / 60)}m${String(Number(s) % 60).padStart(2, "0")}s`);
const fmtNum = (n: unknown) => (n == null ? "—" : Number(n).toLocaleString("pt-BR"));

function useEntityList(type: EntityType) {
  return useQuery({
    queryKey: ["analytics-entities", type],
    queryFn: async () => {
      if (type === "control") {
        const p = await api.get<Page<{ id: number; nome_tabela: string }>>("/api/v1/ingestion-control?page=1&page_size=200");
        return p.items.map((c) => ({ id: c.id, name: c.nome_tabela }));
      }
      if (type === "pipeline") {
        const p = await api.get<Page<{ id: number; name: string }>>("/api/v1/pipelines?page=1&page_size=200");
        return p.items.map((c) => ({ id: c.id, name: c.name }));
      }
      const p = await api.get<Page<{ id: number; name: string }>>("/api/v1/jobs?page=1&page_size=200");
      return p.items.map((c) => ({ id: c.id, name: c.name }));
    },
  });
}

export default function IngestionAnalyticsPage() {
  const navigate = useNavigate();
  const [type, setType] = useState<EntityType>("control");
  const [entityId, setEntityId] = useState<number | null>(null);
  const [days, setDays] = useState(30);

  const entities = useEntityList(type);
  const list = entities.data ?? [];
  const selectedId = entityId ?? list[0]?.id ?? null;

  const history = useQuery({
    queryKey: ["analytics-history", type, selectedId, days],
    queryFn: () => api.get<History>(`/api/v1/observability/history?entity=${type}&id=${selectedId}&days=${days}`),
    enabled: selectedId != null,
  });
  const h = history.data;
  const s = h?.summary ?? {};

  const cards = useMemo(() => ([
    { label: "Execuções", v: s.total_runs, tone: undefined },
    { label: "Taxa de sucesso", v: s.success_rate == null ? "—" : `${s.success_rate}%`, tone: (Number(s.success_rate) < 90 ? "danger" : "success") as any },
    { label: "Falhas", v: s.failed, tone: (Number(s.failed) ? "danger" : undefined) as any },
    { label: "Duração média", v: fmtDur(s.avg_duration_seconds), tone: undefined },
    { label: "Registros gravados", v: fmtNum(s.total_records_written), tone: undefined },
    { label: "Última execução", v: s.last_status ?? "—", tone: (String(s.last_status) === "success" ? "success" : String(s.last_status) === "failed" ? "danger" : undefined) as any },
  ]), [s]);

  return (
    <div>
      <PageHeader
        icon={<LineChart size={22} />}
        title="Análise de Ingestões"
        description="Selecione uma tabela, job ou pipeline e analise o histórico completo das execuções: tendências, volumes, duração e falhas."
      />

      {/* Seletores */}
      <div className="flex flex-wrap items-end gap-3 rounded-2xl border border-gray-100 bg-white p-4">
        <div>
          <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-gray-400">Tipo</div>
          <div className="flex gap-1">
            {TYPES.map((t) => {
              const I = t.icon;
              return (
                <button key={t.key} onClick={() => { setType(t.key); setEntityId(null); }}
                  className={cn("inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                    type === t.key ? "bg-brand-500 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200")}>
                  <I size={15} />{t.label}
                </button>
              );
            })}
          </div>
        </div>
        <div className="min-w-[240px] flex-1">
          <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-gray-400">
            {type === "control" ? "Tabela" : type === "pipeline" ? "Pipeline" : "Job"}
          </div>
          <select value={selectedId ?? ""} onChange={(e) => setEntityId(Number(e.target.value))}
            className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm">
            {list.length === 0 && <option value="">— nada cadastrado —</option>}
            {list.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
          </select>
        </div>
        <div>
          <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-gray-400">Período</div>
          <div className="flex gap-1">
            {WINDOWS.map((w) => (
              <button key={w} onClick={() => setDays(w)}
                className={cn("rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  days === w ? "bg-brand-500 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200")}>
                {w}d
              </button>
            ))}
          </div>
        </div>
      </div>

      {selectedId == null ? (
        <p className="mt-10 text-center text-sm text-gray-400">Selecione uma entidade para ver o histórico.</p>
      ) : (
        <>
          {/* KPIs */}
          <div className="mt-5 grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-6">
            {history.isLoading
              ? Array.from({ length: 6 }).map((_, i) => <MetricCardSkeleton key={i} />)
              : cards.map((c) => <MetricCard key={c.label} label={c.label} value={c.v ?? 0} tone={c.tone} />)}
          </div>

          {/* Gráficos */}
          <div className="mt-6 grid grid-cols-1 gap-4 xl:grid-cols-2">
            <ChartCard title="Execuções por dia" subtitle="verde = sucesso · vermelho = falha">
              <RunsChart series={h?.series ?? []} />
            </ChartCard>
            <ChartCard title="Registros gravados por dia">
              <BarsChart series={h?.series ?? []} field="records_written" color="#0d8a80" />
            </ChartCard>
          </div>

          {/* Tabela de execuções */}
          <div className="mt-6 overflow-hidden rounded-2xl border border-gray-100 bg-white">
            <div className="border-b border-gray-100 px-4 py-2.5 text-sm font-semibold text-gray-800">
              Execuções ({h?.executions.length ?? 0})
            </div>
            <div className="max-h-[460px] overflow-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-gray-50 text-left text-[11px] uppercase tracking-wide text-gray-400">
                  <tr>
                    <Th>#</Th><Th>Status</Th><Th>Início</Th><Th r>Duração</Th><Th r>Lidos</Th>
                    <Th r>Gravados</Th><Th>Watermark</Th><Th>DQ</Th><Th>Trigger</Th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {(h?.executions ?? []).map((r, i) => (
                    <tr key={i} className="cursor-pointer hover:bg-gray-50/60"
                      onClick={() => navigate(`/executions/${r.execution_id}`)}>
                      <Td mono>#{String(r.execution_id)}</Td>
                      <Td><StatusDot s={r.status} />{String(r.status)}</Td>
                      <Td>{fmtDate(r.started_at)}</Td>
                      <Td r>{fmtDur(r.duration_seconds)}</Td>
                      <Td r>{r.records_read == null ? "—" : fmtNum(r.records_read)}</Td>
                      <Td r>{r.records_written == null ? "—" : fmtNum(r.records_written)}</Td>
                      <Td mono>{r.watermark_after == null ? "—" : fmtDate(r.watermark_after)}</Td>
                      <Td>{r.quality ? String(r.quality) : "—"}</Td>
                      <Td>{String(r.trigger_type ?? "—")}</Td>
                    </tr>
                  ))}
                  {(h?.executions ?? []).length === 0 && !history.isLoading && (
                    <tr><td colSpan={9} className="px-3 py-10 text-center text-sm text-gray-400">Nenhuma execução no período.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function ChartCard({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-gray-100 bg-white p-4">
      <div className="mb-3 flex items-baseline justify-between">
        <h3 className="text-sm font-semibold text-gray-800">{title}</h3>
        {subtitle && <span className="text-[11px] text-gray-400">{subtitle}</span>}
      </div>
      {children}
    </div>
  );
}

const CH = 160, GAP = 3;
function RunsChart({ series }: { series: DayPoint[] }) {
  if (series.length === 0) return <Empty />;
  const max = Math.max(1, ...series.map((d) => d.runs));
  const bw = Math.max(6, Math.min(48, Math.floor(720 / series.length) - GAP));
  const w = series.length * (bw + GAP);
  return (
    <div className="overflow-x-auto">
      <svg width={w} height={CH + 22} className="min-w-full">
        {series.map((d, i) => {
          const x = i * (bw + GAP);
          const hOk = (d.success / max) * CH;
          const hFail = (d.failed / max) * CH;
          return (
            <g key={d.date}>
              <rect x={x} y={CH - hFail} width={bw} height={hFail} fill="#dc2626" rx="1" />
              <rect x={x} y={CH - hFail - hOk} width={bw} height={hOk} fill="#0f9d6b" rx="1" />
              <title>{`${d.date}: ${d.runs} execuções (${d.success} ok, ${d.failed} falha)`}</title>
              {(i % Math.ceil(series.length / 12 || 1) === 0) && (
                <text x={x + bw / 2} y={CH + 14} textAnchor="middle" fontSize="9" fill="#94a3b8">{fmtDay(d.date)}</text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}
function BarsChart({ series, field, color }: { series: DayPoint[]; field: keyof DayPoint; color: string }) {
  if (series.length === 0) return <Empty />;
  const vals = series.map((d) => Number(d[field] || 0));
  const max = Math.max(1, ...vals);
  const bw = Math.max(6, Math.min(48, Math.floor(720 / series.length) - GAP));
  const w = series.length * (bw + GAP);
  return (
    <div className="overflow-x-auto">
      <svg width={w} height={CH + 22} className="min-w-full">
        {series.map((d, i) => {
          const x = i * (bw + GAP);
          const bh = (Number(d[field] || 0) / max) * CH;
          return (
            <g key={d.date}>
              <rect x={x} y={CH - bh} width={bw} height={bh} fill={color} rx="1" />
              <title>{`${d.date}: ${Number(d[field] || 0).toLocaleString("pt-BR")}`}</title>
              {(i % Math.ceil(series.length / 12 || 1) === 0) && (
                <text x={x + bw / 2} y={CH + 14} textAnchor="middle" fontSize="9" fill="#94a3b8">{fmtDay(d.date)}</text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}
function Empty() { return <p className="py-12 text-center text-sm text-gray-400">Sem dados no período.</p>; }

function StatusDot({ s }: { s: unknown }) {
  const v = String(s ?? "").toLowerCase();
  const c = v === "success" ? "bg-emerald-500" : v === "failed" || v === "timeout" ? "bg-red-500" : v === "running" ? "bg-sky-500" : "bg-gray-300";
  return <span className={cn("mr-1.5 inline-block h-2 w-2 rounded-full align-middle", c)} />;
}
function Th({ children, r }: { children: React.ReactNode; r?: boolean }) { return <th className={cn("px-3 py-2 font-medium", r && "text-right")}>{children}</th>; }
function Td({ children, r, mono }: { children: React.ReactNode; r?: boolean; mono?: boolean }) {
  return <td className={cn("px-3 py-1.5", r && "text-right tabular-nums", mono && "font-mono text-xs")}>{children}</td>;
}
