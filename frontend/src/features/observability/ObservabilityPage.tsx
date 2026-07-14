import { useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity, AlertTriangle, CheckCircle2, Clock, Database, FileWarning, Gauge, Loader2,
  PlayCircle, RefreshCw, TimerReset, XCircle,
} from "lucide-react";

import { api } from "@/lib/api";
import { PageHeader, MetricCard, SecondaryButton } from "@/components/ui";
import { MetricCardSkeleton } from "@/components/ui/LoadingSkeleton";
import { cn } from "@/lib/cn";

type Row = Record<string, unknown>;
interface Overview {
  date: string;
  summary: Record<string, number>;
  status_distribution: Record<string, number>;
}

const fmtDate = (t: unknown) => (t ? new Date(String(t)).toLocaleString("pt-BR") : "—");
const fmtDur = (s: unknown) => (s == null ? "—" : `${Math.floor(Number(s) / 60)}m ${Number(s) % 60}s`);
const fmtDelay = (m: unknown) => {
  const n = Number(m || 0); if (!n) return "—";
  const h = Math.floor(n / 60), mm = n % 60; return h ? `${h}h${String(mm).padStart(2, "0")}` : `${mm}min`;
};

function useObs<T = Row[]>(path: string) {
  return useQuery({
    queryKey: ["obs", path],
    queryFn: () => api.get<T>(`/api/v1/observability/${path}`),
    refetchInterval: 30_000,
  });
}

function CritChip({ v }: { v: unknown }) {
  const s = String(v ?? "").toLowerCase();
  const cls = s === "critica" ? "bg-red-50 text-red-700" : s === "alta" ? "bg-orange-50 text-orange-700"
    : s === "media" ? "bg-blue-50 text-blue-700" : s === "baixa" ? "bg-gray-100 text-gray-600" : "bg-gray-100 text-gray-400";
  return <span className={cn("rounded px-1.5 py-0.5 text-[10px] font-semibold", cls)}>{s || "—"}</span>;
}
function StatusDot({ s }: { s: unknown }) {
  const v = String(s ?? "").toLowerCase();
  const c = v === "success" ? "bg-emerald-500" : v === "failed" || v === "timeout" ? "bg-red-500"
    : v === "running" ? "bg-sky-500 animate-pulse" : "bg-gray-300";
  return <span className={cn("inline-block h-2 w-2 rounded-full", c)} title={v} />;
}
function ClassChip({ v }: { v: unknown }) {
  const s = String(v ?? "");
  const cls = s === "critico" ? "bg-red-50 text-red-700" : s === "atencao" ? "bg-amber-50 text-amber-700" : "bg-gray-100 text-gray-500";
  return <span className={cn("rounded px-1.5 py-0.5 text-[10px] font-semibold", cls)}>{s}</span>;
}

function Panel({ title, icon, count, children }: { title: string; icon: React.ReactNode; count?: number; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-gray-100 bg-white">
      <div className="flex items-center gap-2 border-b border-gray-100 px-4 py-2.5 text-sm font-semibold text-gray-800">
        {icon}{title}{count != null && <span className="ml-auto rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-500">{count}</span>}
      </div>
      <div className="max-h-[360px] overflow-auto">{children}</div>
    </div>
  );
}
function Empty({ text = "Nada por aqui — tudo saudável." }) { return <p className="px-4 py-6 text-center text-sm text-gray-400">{text}</p>; }
function Th({ children, r }: { children: React.ReactNode; r?: boolean }) { return <th className={cn("px-3 py-2 font-medium", r && "text-right")}>{children}</th>; }
function Td({ children, r, mono }: { children: React.ReactNode; r?: boolean; mono?: boolean }) {
  return <td className={cn("px-3 py-1.5", r && "text-right tabular-nums", mono && "font-mono text-xs")}>{children}</td>;
}
const thead = "sticky top-0 bg-gray-50 text-left text-[11px] uppercase tracking-wide text-gray-400";

export default function ObservabilityPage() {
  const qc = useQueryClient();
  const overview = useQuery({ queryKey: ["obs", "overview"], queryFn: () => api.get<Overview>("/api/v1/observability/overview"), refetchInterval: 30_000 });
  const today = useObs("today");
  const late = useObs("late-loads");
  const sla = useObs("sla");
  const zero = useObs("zero-records");
  const stalled = useObs("watermark-stalled");
  const stFail = useObs<{ items: Row[] }>("source-target-failures");
  const anomalies = useObs("duration-anomalies");
  const dq = useQuery({ queryKey: ["obs", "dq-fail"], queryFn: () => api.get<{ items: Row[] }>("/api/v1/data-quality/results?overall=fail&page=1&page_size=25"), refetchInterval: 60_000 });

  const s = overview.data?.summary ?? {};
  const cards = useMemo(() => ([
    { label: "Rodando agora", v: s.running_now, icon: <PlayCircle size={20} />, tone: undefined },
    { label: "Sucesso hoje", v: s.success_today, icon: <CheckCircle2 size={20} />, tone: "success" as const },
    { label: "Falhas hoje", v: s.failed_today, icon: <XCircle size={20} />, tone: "danger" as const },
    { label: "Atrasadas", v: s.late_loads, icon: <Clock size={20} />, tone: (s.late_loads ? "danger" : undefined) as any },
    { label: "Fora do SLA", v: s.sla_breaches, icon: <Gauge size={20} />, tone: (s.sla_breaches ? "danger" : undefined) as any },
    { label: "Zero registros", v: s.zero_record_runs, icon: <FileWarning size={20} />, tone: undefined },
    { label: "Watermark parado", v: s.watermark_stalled, icon: <TimerReset size={20} />, tone: undefined },
    { label: "Críticas c/ erro", v: s.critical_failures, icon: <AlertTriangle size={20} />, tone: (s.critical_failures ? "danger" : undefined) as any },
  ]), [s]);

  function refreshAll() { qc.invalidateQueries({ queryKey: ["obs"] }); }

  return (
    <div>
      <PageHeader
        icon={<Activity size={22} />}
        title="Observabilidade Operacional"
        description="Acompanhe a saúde das cargas, SLAs, falhas, atrasos e qualidade operacional das ingestões."
        actions={<SecondaryButton icon={<RefreshCw size={16} />} onClick={refreshAll}>Atualizar</SecondaryButton>}
      />

      {overview.isLoading ? (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">{Array.from({ length: 8 }).map((_, i) => <MetricCardSkeleton key={i} />)}</div>
      ) : (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {cards.map((c) => <MetricCard key={c.label} label={c.label} value={c.v ?? 0} icon={c.icon} tone={c.tone} />)}
        </div>
      )}

      <div className="mt-6 grid grid-cols-1 gap-4 xl:grid-cols-2">
        {/* Saúde do dia */}
        <div className="xl:col-span-2">
          <Panel title="Saúde do dia" icon={<Activity size={15} className="text-brand-500" />} count={(today.data ?? []).length}>
            {today.isLoading ? <Loading /> : (today.data ?? []).length === 0 ? <Empty text="Nenhuma execução hoje." /> : (
              <table className="w-full text-sm">
                <thead className={thead}><tr><Th>Carga</Th><Th>Grupo</Th><Th>Crit.</Th><Th>Status</Th><Th>Início</Th><Th r>Dur.</Th><Th r>Lidos</Th><Th r>Gravados</Th></tr></thead>
                <tbody className="divide-y divide-gray-50">
                  {(today.data ?? []).map((r, i) => (
                    <tr key={i} className="hover:bg-gray-50/60">
                      <Td mono>{String(r.carga ?? "—")}</Td><Td>{String(r.grupo ?? "—")}</Td>
                      <Td><CritChip v={r.criticidade} /></Td>
                      <Td><span className="inline-flex items-center gap-1.5"><StatusDot s={r.status} />{String(r.status)}</span></Td>
                      <Td>{fmtDate(r.started_at)}</Td><Td r>{fmtDur(r.duration_seconds)}</Td>
                      <Td r>{r.records_read == null ? "—" : String(r.records_read)}</Td><Td r>{r.records_written == null ? "—" : String(r.records_written)}</Td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Panel>
        </div>

        <Panel title="Cargas atrasadas" icon={<Clock size={15} className="text-red-500" />} count={(late.data ?? []).length}>
          {late.isLoading ? <Loading /> : (late.data ?? []).length === 0 ? <Empty /> : (
            <table className="w-full text-sm">
              <thead className={thead}><tr><Th>Carga</Th><Th>Freq.</Th><Th>Última exec.</Th><Th r>Atraso</Th><Th>Crit.</Th></tr></thead>
              <tbody className="divide-y divide-gray-50">
                {(late.data ?? []).map((r, i) => (
                  <tr key={i}><Td mono>{String(r.carga)}</Td><Td>{String(r.expected_frequency ?? "—")}</Td>
                    <Td>{fmtDate(r.last_execution_at)}</Td><Td r>{fmtDelay(r.delay_minutes)}</Td><Td><CritChip v={r.criticidade} /></Td></tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>

        <Panel title="Fora do SLA" icon={<Gauge size={15} className="text-orange-500" />} count={(sla.data ?? []).length}>
          {sla.isLoading ? <Loading /> : (sla.data ?? []).length === 0 ? <Empty /> : (
            <table className="w-full text-sm">
              <thead className={thead}><tr><Th>Carga</Th><Th r>SLA</Th><Th r>Duração</Th><Th r>Excedeu</Th></tr></thead>
              <tbody className="divide-y divide-gray-50">
                {(sla.data ?? []).map((r, i) => (
                  <tr key={i}><Td mono>{String(r.carga)}</Td><Td r>{String(r.sla_minutes)}min</Td>
                    <Td r>{fmtDur(r.duration_seconds)}</Td><Td r>{fmtDur(r.exceeded_seconds)}</Td></tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>

        <Panel title="Zero registros" icon={<FileWarning size={15} className="text-amber-500" />} count={(zero.data ?? []).length}>
          {zero.isLoading ? <Loading /> : (zero.data ?? []).length === 0 ? <Empty /> : (
            <table className="w-full text-sm">
              <thead className={thead}><tr><Th>Carga</Th><Th>Tipo</Th><Th r>Lidos</Th><Th r>Gravados</Th><Th>Classe</Th></tr></thead>
              <tbody className="divide-y divide-gray-50">
                {(zero.data ?? []).map((r, i) => (
                  <tr key={i}><Td mono>{String(r.carga)}</Td><Td>{String(r.tipo_ingestao ?? "—")}</Td>
                    <Td r>{r.records_read == null ? "—" : String(r.records_read)}</Td><Td r>{r.records_written == null ? "—" : String(r.records_written)}</Td><Td><ClassChip v={r.classificacao} /></Td></tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>

        <Panel title="Watermark parado" icon={<TimerReset size={15} className="text-violet-500" />} count={(stalled.data ?? []).length}>
          {stalled.isLoading ? <Loading /> : (stalled.data ?? []).length === 0 ? <Empty /> : (
            <table className="w-full text-sm">
              <thead className={thead}><tr><Th>Carga</Th><Th>Watermark atual</Th><Th>Última exec.</Th><Th>Crit.</Th></tr></thead>
              <tbody className="divide-y divide-gray-50">
                {(stalled.data ?? []).map((r, i) => (
                  <tr key={i}><Td mono>{String(r.carga)}</Td><Td mono>{fmtDate(r.watermark_atual)}</Td>
                    <Td>{fmtDate(r.last_execution_at)}</Td><Td><CritChip v={r.criticidade} /></Td></tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>

        <Panel title="Falhas por origem/destino" icon={<Database size={15} className="text-red-500" />} count={(stFail.data?.items ?? []).length}>
          {stFail.isLoading ? <Loading /> : (stFail.data?.items ?? []).length === 0 ? <Empty /> : (
            <table className="w-full text-sm">
              <thead className={thead}><tr><Th>Conexão</Th><Th>Papel</Th><Th r>Falhas</Th><Th>Última msg</Th></tr></thead>
              <tbody className="divide-y divide-gray-50">
                {(stFail.data?.items ?? []).map((r, i) => (
                  <tr key={i}><Td>{String(r.connection)}</Td><Td>{String(r.role)}</Td><Td r>{Number(r.failures_today)}</Td>
                    <Td><span className="line-clamp-1 text-xs text-gray-500">{String(r.last_message ?? "—")}</span></Td></tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>

        <Panel title="Duração fora do normal" icon={<Gauge size={15} className="text-orange-500" />} count={(anomalies.data ?? []).length}>
          {anomalies.isLoading ? <Loading /> : (anomalies.data ?? []).length === 0 ? <Empty /> : (
            <table className="w-full text-sm">
              <thead className={thead}><tr><Th>Carga</Th><Th r>Duração</Th><Th r>Média</Th><Th r>×</Th></tr></thead>
              <tbody className="divide-y divide-gray-50">
                {(anomalies.data ?? []).map((r, i) => (
                  <tr key={i}><Td mono>{String(r.carga)}</Td><Td r>{fmtDur(r.duration_seconds)}</Td>
                    <Td r>{fmtDur(r.avg_seconds)}</Td><Td r>{String(r.ratio)}×</Td></tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>

        <Panel title="Qualidade — problemas em Data Lake / cargas" icon={<AlertTriangle size={15} className="text-red-500" />} count={(dq.data?.items ?? []).length}>
          {dq.isLoading ? <Loading /> : (dq.data?.items ?? []).length === 0 ? <Empty text="Sem falhas de qualidade recentes." /> : (
            <table className="w-full text-sm">
              <thead className={thead}><tr><Th>Carga</Th><Th>Checks com falha</Th><Th>Quando</Th></tr></thead>
              <tbody className="divide-y divide-gray-50">
                {(dq.data?.items ?? []).map((r: Row, i) => {
                  const checks = (r.checks as Row[] | undefined) ?? [];
                  const failed = checks.filter((c) => String(c.status) === "fail").map((c) => String(c.name));
                  return (
                    <tr key={i}><Td mono>{String(r.table_name ?? r.job_name ?? "—")}</Td>
                      <Td><span className="text-xs text-red-600">{failed.join(", ") || "—"}</span></Td>
                      <Td>{fmtDate(r.created_at)}</Td></tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </Panel>
      </div>
    </div>
  );
}

const Loading = () => (
  <div className="flex items-center gap-2 px-4 py-6 text-sm text-gray-400"><Loader2 size={15} className="animate-spin" /> Carregando…</div>
);
