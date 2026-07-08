import { useState } from "react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import {
  Activity,
  Braces,
  CalendarPlus,
  Check,
  ChevronRight,
  Code2,
  Copy,
  FileCode2,
  ListChecks,
  Pencil,
  Play,
  PlayCircle,
  Settings2,
  Tag as TagIcon,
  Terminal,
  Zap,
} from "lucide-react";

import { Card, PrimaryButton, StatusBadge } from "@/components/ui";
import { TagBadges } from "@/components/ui/TagBadges";
import { cn } from "@/lib/cn";
import { useAuth } from "@/lib/auth";
import { JOB_TYPE_LABEL, fmtDate, fmtDuration, parseJobArguments } from "@/features/jobs/types";
import type { JobDetail } from "@/features/jobs/types";
import { JobConnectionBox } from "@/features/jobs/JobConnectionBox";

type TabKey = "overview" | "executions" | "schedules" | "code" | "settings";

/* ── small building blocks ── */
function SectionCard({ icon, title, action, children, className }: {
  icon: ReactNode; title: string; action?: ReactNode; children: ReactNode; className?: string;
}) {
  return (
    <Card className={cn("p-5", className)}>
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-gray-900">
          <span className="text-brand-500">{icon}</span>{title}
        </h2>
        {action}
      </div>
      {children}
    </Card>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-gray-400">{label}</dt>
      <dd className="mt-1 text-sm text-gray-800">{children}</dd>
    </div>
  );
}

function Muted({ children }: { children: ReactNode }) {
  return <span className="text-sm text-gray-400">{children}</span>;
}

function CopyBtn({ text, label = "Copiar" }: { text: string; label?: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      onClick={async () => { try { await navigator.clipboard.writeText(text); setDone(true); setTimeout(() => setDone(false), 1500); } catch { /* */ } }}
      className="inline-flex items-center gap-1.5 rounded-md border border-gray-200 bg-white px-2.5 py-1 text-xs font-medium text-gray-600 transition-colors hover:bg-gray-50 hover:text-gray-900"
    >
      {done ? <Check size={13} className="text-emerald-500" /> : <Copy size={13} />} {done ? "Copiado" : label}
    </button>
  );
}

function MetricCard({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <Card className="p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-gray-400">{label}</p>
      <div className="mt-2 text-2xl font-bold text-gray-900">{children}</div>
      {hint && <p className="mt-1 text-xs text-gray-400">{hint}</p>}
    </Card>
  );
}

/* ── health ── */
function health(job: JobDetail): { tone: string; label: string; text: string } {
  if (job.executions_total === 0)
    return { tone: "gray", label: "Sem histórico", text: "Este job ainda não foi executado." };
  if (["failed", "timeout"].includes(job.last_status ?? ""))
    return { tone: "red", label: "Crítica", text: "A última execução falhou." };
  if (job.last_status === "success" && job.recent_failures > 0)
    return { tone: "amber", label: "Atenção", text: "Último sucesso, mas houve falhas recentes." };
  if (job.last_status === "success")
    return { tone: "green", label: "Boa", text: "Última execução com sucesso e sem falhas recentes." };
  return { tone: "gray", label: "—", text: "Estado indeterminado." };
}
const TONE: Record<string, string> = {
  green: "border-emerald-200 bg-emerald-50 text-emerald-700",
  amber: "border-amber-200 bg-amber-50 text-amber-700",
  red: "border-red-200 bg-red-50 text-red-700",
  gray: "border-gray-200 bg-gray-50 text-gray-600",
};

/* ── main ── */
export function JobOverviewTab({
  job, canRun, running, onRun, onEdit, onOpenCode, onGoTab,
}: {
  job: JobDetail;
  canRun: boolean;
  running: boolean;
  onRun: () => void;
  onEdit: () => void;
  onOpenCode: () => void;
  onGoTab: (t: TabKey) => void;
}) {
  const navigate = useNavigate();
  const { can } = useAuth();
  const params = (job.default_parameters ?? {}) as Record<string, unknown>;
  const paramKeys = Object.keys(params);
  const { raw, lines, pairs } = parseJobArguments(job.arguments);
  const [structured, setStructured] = useState(false);
  const h = health(job);
  const modo = job.engine === "spark_cluster" ? "Spark cluster" : job.engine === "python_worker" ? "Python worker" : (job.engine ?? "Não configurado");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-bold text-gray-900">Visão geral do job</h1>
        <p className="mt-0.5 text-sm text-gray-500">Acompanhe a saúde, execuções, conexões e principais configurações deste job.</p>
      </div>

      {/* Resumo */}
      <SectionCard icon={<ListChecks size={15} />} title="Resumo do job">
        <div className="flex flex-wrap items-center gap-2">
          <span className="inline-flex rounded-md bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-700">{JOB_TYPE_LABEL[job.type] ?? job.type}</span>
          {job.engine && <span className="inline-flex rounded-md bg-gray-100 px-2 py-0.5 font-mono text-xs text-gray-700">{job.engine}</span>}
          <StatusBadge status={job.is_active ? "active" : "inactive"} />
          {(job.tags ?? []).length > 0 && <TagBadges tags={job.tags ?? []} max={12} />}
        </div>
        {job.description && <p className="mt-3 text-sm text-gray-600">{job.description}</p>}
        <div className="mt-4">
          <dt className="mb-1 text-xs font-medium uppercase tracking-wide text-gray-400">Script principal</dt>
          {job.script_path ? (
            <div className="flex items-start gap-2 rounded-lg border border-graphite-800 bg-graphite-950 px-3 py-2">
              <FileCode2 size={14} className="mt-0.5 shrink-0 text-brand-400" />
              <code className="min-w-0 flex-1 break-all font-mono text-xs text-slate-200">{job.script_path}</code>
              <div className="shrink-0"><CopyBtn text={job.script_path} /></div>
            </div>
          ) : <Muted>Não configurado</Muted>}
        </div>
      </SectionCard>

      {/* Métricas */}
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <MetricCard label="Total de execuções">{job.executions_total}</MetricCard>
        <MetricCard label="Último status">
          {job.last_status ? <StatusBadge status={job.last_status} /> : <span className="text-base font-medium text-gray-400">Nenhuma execução</span>}
        </MetricCard>
        <MetricCard label="Tempo médio de sucesso">{job.avg_duration_seconds != null ? fmtDuration(job.avg_duration_seconds) : <span className="text-base font-medium text-gray-400">—</span>}</MetricCard>
        <MetricCard label="Última execução">
          <span className="text-base font-medium">{job.last_finished_at ? fmtDate(job.last_finished_at) : <span className="text-gray-400">Nenhuma execução</span>}</span>
        </MetricCard>
      </div>

      {/* Última execução + Saúde */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <SectionCard icon={<PlayCircle size={15} />} title="Última execução">
          {job.last_execution_id ? (
            <div>
              <div className="flex items-center justify-between">
                <span className="text-lg font-bold text-gray-900">Execução #{job.last_execution_id}</span>
                <StatusBadge status={job.last_status ?? "queued"} />
              </div>
              <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3">
                <Field label="Data/hora">{fmtDate(job.last_finished_at ?? job.last_execution_started_at)}</Field>
                <Field label="Duração">{fmtDuration(job.last_execution_duration_seconds)}</Field>
                <Field label="Disparado por">{job.last_execution_trigger ?? "—"}</Field>
                <Field label="Engine"><span className="font-mono text-xs">{job.last_execution_engine ?? "—"}</span></Field>
              </dl>
              <button onClick={() => navigate(`/executions/${job.last_execution_id}`)}
                className="mt-4 inline-flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50">
                Ver detalhes da execução <ChevronRight size={15} />
              </button>
            </div>
          ) : (
            <Muted>Este job ainda não possui execuções.</Muted>
          )}
        </SectionCard>

        <SectionCard icon={<Activity size={15} />} title="Saúde operacional">
          <div className={cn("mb-4 flex items-center justify-between rounded-lg border px-3 py-2 text-sm font-medium", TONE[h.tone])}>
            <span>{h.label}</span>
            <span className="text-xs font-normal opacity-80">{h.text}</span>
          </div>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-3">
            <Field label="Último status">{job.last_status ? <StatusBadge status={job.last_status} /> : <Muted>—</Muted>}</Field>
            <Field label="Taxa de sucesso">{job.success_rate != null ? `${job.success_rate}%` : <Muted>Sem dados</Muted>}</Field>
            <Field label="Falhas recentes">{job.recent_failures > 0 ? `${job.recent_failures} nos últimos 7 dias` : "Nenhuma nos últimos 7 dias"}</Field>
            <Field label="Execuções em andamento">{job.running_executions}</Field>
            <Field label="Schedules ativos">{job.active_schedules}</Field>
          </dl>
        </SectionCard>
      </div>

      {/* Conexões */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <SectionCard icon={<Zap size={15} />} title="Conexão origem">
          <JobConnectionBox role="Origem" c={job.source_connection} />
        </SectionCard>
        <SectionCard icon={<Zap size={15} />} title="Conexão destino">
          <JobConnectionBox role="Destino" c={job.target_connection} />
        </SectionCard>
      </div>

      {/* Configuração principal */}
      <SectionCard icon={<Settings2 size={15} />} title="Configuração principal">
        <dl className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-4">
          <Field label="Tipo do job">{JOB_TYPE_LABEL[job.type] ?? job.type}</Field>
          <Field label="Engine"><span className="font-mono text-xs">{job.engine ?? <Muted>Não configurado</Muted>}</span></Field>
          <Field label="Cluster ID">{job.cluster_id ?? <Muted>Não configurado</Muted>}</Field>
          <Field label="Timeout">{job.timeout_seconds ? `${job.timeout_seconds}s` : <Muted>Sem limite definido</Muted>}</Field>
          <Field label="Retry">{job.retry_count > 0 ? `${job.retry_count} tentativa(s)` : <Muted>Nenhuma tentativa extra</Muted>}</Field>
          <Field label="Classe principal">{job.main_class ? <span className="font-mono text-xs">{job.main_class}</span> : <Muted>Não aplicável</Muted>}</Field>
          <Field label="Modo de execução">{modo}</Field>
          <Field label="Criado por">{job.created_by ?? <Muted>—</Muted>}</Field>
        </dl>
      </SectionCard>

      {/* Parâmetros e argumentos */}
      <SectionCard
        icon={<Terminal size={15} />}
        title="Parâmetros e argumentos"
        action={raw ? (
          <div className="flex items-center gap-2">
            <button onClick={() => setStructured((v) => !v)} className="inline-flex items-center gap-1.5 rounded-md border border-gray-200 bg-white px-2.5 py-1 text-xs font-medium text-gray-600 hover:bg-gray-50">
              <Braces size={13} /> {structured ? "Ver comando" : "Ver estruturado"}
            </button>
            <CopyBtn text={raw} label="Copiar argumentos" />
          </div>
        ) : undefined}
      >
        <dt className="mb-1 text-xs font-medium uppercase tracking-wide text-gray-400">Parâmetros padrão</dt>
        {paramKeys.length === 0 ? (
          <p className="mb-4 text-sm text-gray-400">Nenhum parâmetro padrão definido.</p>
        ) : (
          <div className="mb-4 mt-1 space-y-1">
            {paramKeys.map((k) => (
              <div key={k} className="flex justify-between gap-3 font-mono text-xs">
                <span className="text-gray-500">{k}</span>
                <span className="truncate text-gray-800">{String(params[k])}</span>
              </div>
            ))}
          </div>
        )}
        <dt className="mb-1 text-xs font-medium uppercase tracking-wide text-gray-400">Argumentos</dt>
        {!raw ? (
          <Muted>Nenhum argumento configurado</Muted>
        ) : structured ? (
          <div className="divide-y divide-gray-100 rounded-lg border border-gray-100">
            {pairs.map((p) => (
              <div key={p.key} className="flex items-center justify-between gap-4 px-3 py-2 text-sm">
                <span className="font-mono text-xs text-gray-500">{p.key}</span>
                <span className="truncate font-mono text-xs text-gray-800">{p.value}</span>
              </div>
            ))}
          </div>
        ) : (
          <pre className="overflow-x-auto rounded-lg border border-graphite-800 bg-graphite-950 p-3 font-mono text-xs leading-relaxed text-slate-200">
{lines.map((l, i) => `${l}${i < lines.length - 1 ? " \\" : ""}`).join("\n")}
          </pre>
        )}
      </SectionCard>

      {/* Tags + Ações rápidas */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <SectionCard
          icon={<TagIcon size={15} />}
          title="Tags"
          action={<button onClick={() => onGoTab("settings")} className="text-xs font-medium text-brand-600 hover:text-brand-700">Gerenciar tags</button>}
        >
          {(job.tags ?? []).length > 0 ? <TagBadges tags={job.tags ?? []} max={20} /> : <Muted>Nenhuma tag cadastrada.</Muted>}
        </SectionCard>

        <SectionCard icon={<Zap size={15} />} title="Ações rápidas">
          <div className="flex flex-wrap gap-2">
            {canRun && (
              <PrimaryButton size="sm" icon={<Play size={14} />} loading={running} disabled={!job.is_active} onClick={onRun}>Executar job</PrimaryButton>
            )}
            <QuickBtn icon={<PlayCircle size={14} />} onClick={() => onGoTab("executions")}>Ver execuções</QuickBtn>
            {can("ingest:jobs:code:read") && <QuickBtn icon={<Code2 size={14} />} onClick={onOpenCode}>Abrir código</QuickBtn>}
            {can("ingest:write") && <QuickBtn icon={<Pencil size={14} />} onClick={onEdit}>Editar configurações</QuickBtn>}
            {can("ingest:schedules:write") && <QuickBtn icon={<CalendarPlus size={14} />} onClick={() => onGoTab("schedules")}>Criar agendamento</QuickBtn>}
          </div>
        </SectionCard>
      </div>
    </div>
  );
}

function QuickBtn({ icon, children, onClick }: { icon: ReactNode; children: ReactNode; onClick: () => void }) {
  return (
    <button onClick={onClick} className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 text-xs font-medium text-gray-600 transition-colors hover:bg-gray-50 hover:text-gray-900">
      {icon} {children}
    </button>
  );
}
