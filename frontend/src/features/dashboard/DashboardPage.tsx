import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  Activity, AlertTriangle, CalendarClock, CheckCircle2, Clock, Cpu, Database,
  GaugeCircle, LayoutDashboard, Loader2, PlayCircle, Server, TrendingDown, XCircle, Zap,
} from "lucide-react";

import { api } from "@/lib/api";
import { Card, PageHeader, StatusBadge } from "@/components/ui";
import { cn } from "@/lib/cn";

interface OpExec { id: number; name: string | null; status: string; engine: string | null; trigger_type: string | null; started_at: string | null; finished_at: string | null; duration_seconds: number | null }
interface OpPipe { id: number; pipeline_id: number | null; name: string | null; started_at: string | null }
interface OpSchedule { id: number; name: string; job_id: number | null; job_name: string | null; next_run_at: string | null; minutes_late: number | null }
interface OpSlow { execution_id: number; name: string | null; duration_seconds: number | null; avg_seconds: number | null; factor: number | null }
interface OpZero { execution_id: number; name: string | null; finished_at: string | null }
interface OpCluster { name: string | null; status: string | null; workers_detected: number; workers_expected: number; cores_total: number; memory_total: string | null }
interface Operational {
  generated_at: string; running_jobs: number; running_pipelines: number;
  executions_today: number; success_today: number; failed_today: number;
  failures_7d: number; jobs_with_error_7d: number; pipelines_with_error_7d: number;
  records_read_today: number; records_written_today: number; avg_duration_seconds: number | null;
  status_distribution: Record<string, number>;
  running_jobs_list: OpExec[]; running_pipelines_list: OpPipe[];
  recent_executions: OpExec[]; recent_failures: OpExec[];
  schedules_overdue: OpSchedule[]; schedules_upcoming: OpSchedule[];
  zero_record_jobs: OpZero[]; slow_jobs: OpSlow[]; cluster: OpCluster | null;
}

function fmtDur(s: number | null): string {
  if (s == null) return "—";
  if (s < 60) return `${Math.round(s * 10) / 10}s`.replace(".", ",");
  const m = Math.floor(s / 60); const sec = Math.round(s % 60);
  return sec ? `${m}min ${sec}s` : `${m}min`;
}
function fmtTime(t: string | null): string { return t ? new Date(t).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : "—"; }
function nf(n: number): string { return n.toLocaleString("pt-BR"); }

const STATUS_BAR: Record<string, string> = {
  success: "bg-emerald-500", failed: "bg-red-500", timeout: "bg-amber-500",
  running: "bg-brand-500", queued: "bg-sky-500", cancelled: "bg-gray-400", skipped: "bg-gray-300",
};

function Kpi({ icon, label, value, hint, tone }: { icon: React.ReactNode; label: string; value: React.ReactNode; hint?: string; tone?: string }) {
  return (
    <Card className="p-4">
      <div className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-gray-400">
        <span className="text-gray-400">{icon}</span>{label}
      </div>
      <p className={cn("mt-2 text-2xl font-bold", tone ?? "text-gray-900")}>{value}</p>
      {hint && <p className="mt-0.5 text-xs text-gray-400">{hint}</p>}
    </Card>
  );
}

function Panel({ icon, title, count, children, action }: { icon: React.ReactNode; title: string; count?: number; children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <Card className="p-5">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-gray-900">
          <span className="text-brand-500">{icon}</span>{title}
          {count != null && <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-500">{count}</span>}
        </h2>
        {action}
      </div>
      {children}
    </Card>
  );
}

function ExecRow({ e }: { e: OpExec }) {
  return (
    <Link to={`/executions/${e.id}`} className="flex items-center justify-between gap-3 border-b border-gray-50 py-2 last:border-0 hover:bg-gray-50/60">
      <div className="min-w-0">
        <p className="truncate text-sm text-gray-800">{e.name ?? `Execução #${e.id}`}</p>
        <p className="text-xs text-gray-400">{fmtTime(e.finished_at ?? e.started_at)}{e.duration_seconds != null ? ` · ${fmtDur(e.duration_seconds)}` : ""}</p>
      </div>
      <StatusBadge status={e.status} />
    </Link>
  );
}

export default function DashboardPage() {
  const { data: d, isLoading } = useQuery({
    queryKey: ["dashboard-operational"],
    queryFn: () => api.get<Operational>("/api/v1/dashboard/operational"),
    refetchInterval: 30000,
    refetchIntervalInBackground: false,
  });

  if (isLoading || !d) {
    return (
      <div>
        <PageHeader icon={<LayoutDashboard size={22} />} title="Dashboard operacional" description="Carregando…" />
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-6">{Array.from({ length: 6 }).map((_, i) => <div key={i} className="h-24 animate-pulse rounded-2xl bg-gray-100" />)}</div>
      </div>
    );
  }

  const distTotal = Object.values(d.status_distribution).reduce((a, b) => a + b, 0) || 1;

  return (
    <div>
      <PageHeader
        icon={<LayoutDashboard size={22} />}
        title="Dashboard operacional"
        description="O que está rodando, o que falhou e o que está atrasado — atualização automática."
        actions={<span className="text-xs text-gray-400">Atualizado {fmtTime(d.generated_at)}</span>}
      />

      {/* KPIs */}
      <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Kpi icon={<Loader2 size={14} />} label="Rodando agora" value={d.running_jobs + d.running_pipelines} hint={`${d.running_jobs} jobs · ${d.running_pipelines} pipelines`} tone={d.running_jobs + d.running_pipelines ? "text-brand-600" : undefined} />
        <Kpi icon={<PlayCircle size={14} />} label="Execuções hoje" value={nf(d.executions_today)} hint={`${d.success_today} ok · ${d.failed_today} falha`} />
        <Kpi icon={<XCircle size={14} />} label="Falhas (7d)" value={nf(d.failures_7d)} hint={`${d.jobs_with_error_7d} jobs · ${d.pipelines_with_error_7d} pipelines`} tone={d.failures_7d ? "text-red-600" : undefined} />
        <Kpi icon={<Clock size={14} />} label="Tempo médio" value={fmtDur(d.avg_duration_seconds)} />
        <Kpi icon={<TrendingDown size={14} />} label="Lidos hoje" value={nf(d.records_read_today)} />
        <Kpi icon={<Database size={14} />} label="Gravados hoje" value={nf(d.records_written_today)} />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Rodando agora */}
        <Panel icon={<Activity size={15} />} title="Rodando agora" count={d.running_jobs + d.running_pipelines}>
          {d.running_jobs_list.length + d.running_pipelines_list.length === 0 ? (
            <p className="py-2 text-sm text-gray-400">Nada em execução no momento.</p>
          ) : (
            <div>
              {d.running_pipelines_list.map((p) => (
                <Link key={`p${p.id}`} to={`/executions/${p.id}`} className="flex items-center justify-between border-b border-gray-50 py-2 last:border-0 hover:bg-gray-50/60">
                  <span className="flex items-center gap-2 text-sm text-gray-800"><Zap size={13} className="text-brand-500" /> {p.name ?? `Pipeline #${p.pipeline_id}`}</span>
                  <span className="text-xs text-gray-400">{fmtTime(p.started_at)}</span>
                </Link>
              ))}
              {d.running_jobs_list.map((e) => <ExecRow key={e.id} e={e} />)}
            </div>
          )}
        </Panel>

        {/* Falhas recentes */}
        <Panel icon={<AlertTriangle size={15} />} title="Falhas recentes" count={d.recent_failures.length}
          action={<Link to="/executions" className="text-xs font-medium text-brand-600 hover:text-brand-700">Ver todas</Link>}>
          {d.recent_failures.length === 0 ? (
            <p className="py-2 text-sm text-emerald-600">Sem falhas recentes.</p>
          ) : d.recent_failures.map((e) => <ExecRow key={e.id} e={e} />)}
        </Panel>

        {/* Cluster */}
        <Panel icon={<Server size={15} />} title="Cluster Spark">
          {!d.cluster ? <p className="py-2 text-sm text-gray-400">Nenhum cluster.</p> : (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-800">{d.cluster.name}</span>
                <span className={cn("inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium",
                  d.cluster.status === "active" ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-red-200 bg-red-50 text-red-700")}>
                  <span className={cn("h-1.5 w-1.5 rounded-full", d.cluster.status === "active" ? "bg-emerald-500" : "bg-red-500")} />
                  {d.cluster.status === "active" ? "Ativo" : "Inacessível"}
                </span>
              </div>
              <div className="grid grid-cols-3 gap-2 text-center">
                <div className="rounded-lg bg-gray-50 py-2"><p className="text-lg font-bold text-gray-900">{d.cluster.workers_detected}/{d.cluster.workers_expected}</p><p className="text-[11px] text-gray-400">workers</p></div>
                <div className="rounded-lg bg-gray-50 py-2"><p className="text-lg font-bold text-gray-900">{d.cluster.cores_total}</p><p className="text-[11px] text-gray-400">cores</p></div>
                <div className="rounded-lg bg-gray-50 py-2"><p className="text-lg font-bold text-gray-900">{d.cluster.memory_total ?? "—"}</p><p className="text-[11px] text-gray-400">memória</p></div>
              </div>
              {d.cluster.workers_detected < d.cluster.workers_expected && (
                <p className="flex items-center gap-1.5 text-xs text-amber-600"><AlertTriangle size={13} /> Menos workers que o esperado.</p>
              )}
            </div>
          )}
        </Panel>

        {/* Schedules atrasados */}
        <Panel icon={<CalendarClock size={15} />} title="Schedules atrasados" count={d.schedules_overdue.length}>
          {d.schedules_overdue.length === 0 ? (
            <p className="py-2 text-sm text-gray-400">Nenhum schedule atrasado.</p>
          ) : d.schedules_overdue.map((s) => (
            <Link key={s.id} to={s.job_id ? `/jobs/${s.job_id}` : "/schedules"} className="flex items-center justify-between border-b border-gray-50 py-2 last:border-0 hover:bg-gray-50/60">
              <div><p className="text-sm text-gray-800">{s.name}</p><p className="text-xs text-gray-400">{s.job_name ?? ""}</p></div>
              <span className="text-xs font-medium text-amber-600">{s.minutes_late}min atrasado</span>
            </Link>
          ))}
        </Panel>

        {/* Próximos schedules */}
        <Panel icon={<CalendarClock size={15} />} title="Próximos agendamentos" count={d.schedules_upcoming.length}
          action={<Link to="/schedules" className="text-xs font-medium text-brand-600 hover:text-brand-700">Ver todos</Link>}>
          {d.schedules_upcoming.length === 0 ? (
            <p className="py-2 text-sm text-gray-400">Nenhum agendamento próximo.</p>
          ) : d.schedules_upcoming.map((s) => (
            <div key={s.id} className="flex items-center justify-between border-b border-gray-50 py-2 last:border-0">
              <div><p className="text-sm text-gray-800">{s.name}</p><p className="text-xs text-gray-400">{s.job_name ?? ""}</p></div>
              <span className="text-xs text-gray-500">{fmtTime(s.next_run_at)}</span>
            </div>
          ))}
        </Panel>

        {/* Distribuição de status (7d) */}
        <Panel icon={<GaugeCircle size={15} />} title="Execuções por status (7 dias)">
          <div className="space-y-2">
            {Object.entries(d.status_distribution).sort((a, b) => b[1] - a[1]).map(([s, c]) => (
              <div key={s} className="flex items-center gap-2">
                <span className="w-20 shrink-0 text-xs text-gray-500">{s}</span>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-gray-100">
                  <div className={cn("h-full rounded-full", STATUS_BAR[s] ?? "bg-gray-400")} style={{ width: `${(c / distTotal) * 100}%` }} />
                </div>
                <span className="w-8 shrink-0 text-right text-xs font-medium text-gray-700">{c}</span>
              </div>
            ))}
            {Object.keys(d.status_distribution).length === 0 && <p className="py-2 text-sm text-gray-400">Sem execuções no período.</p>}
          </div>
        </Panel>

        {/* Zero registros */}
        <Panel icon={<TrendingDown size={15} />} title="Cargas com zero registros" count={d.zero_record_jobs.length}>
          {d.zero_record_jobs.length === 0 ? (
            <p className="py-2 text-sm text-gray-400">Nenhuma carga zerada hoje.</p>
          ) : d.zero_record_jobs.map((z) => (
            <Link key={z.execution_id} to={`/executions/${z.execution_id}`} className="flex items-center justify-between border-b border-gray-50 py-2 last:border-0 hover:bg-gray-50/60">
              <span className="truncate text-sm text-gray-800">{z.name}</span>
              <span className="text-xs text-gray-400">{fmtTime(z.finished_at)}</span>
            </Link>
          ))}
        </Panel>

        {/* Jobs lentos */}
        <Panel icon={<Cpu size={15} />} title="Acima do tempo normal" count={d.slow_jobs.length}>
          {d.slow_jobs.length === 0 ? (
            <p className="py-2 text-sm text-gray-400">Nada fora do normal.</p>
          ) : d.slow_jobs.map((s) => (
            <Link key={s.execution_id} to={`/executions/${s.execution_id}`} className="flex items-center justify-between border-b border-gray-50 py-2 last:border-0 hover:bg-gray-50/60">
              <span className="truncate text-sm text-gray-800">{s.name}</span>
              <span className="text-xs font-medium text-amber-600">{fmtDur(s.duration_seconds)} · {s.factor}× média</span>
            </Link>
          ))}
        </Panel>

        {/* Últimas execuções */}
        <Panel icon={<CheckCircle2 size={15} />} title="Últimas execuções"
          action={<Link to="/executions" className="text-xs font-medium text-brand-600 hover:text-brand-700">Ver todas</Link>}>
          {d.recent_executions.length === 0 ? (
            <p className="py-2 text-sm text-gray-400">Nenhuma execução ainda.</p>
          ) : d.recent_executions.map((e) => <ExecRow key={e.id} e={e} />)}
        </Panel>
      </div>
    </div>
  );
}
