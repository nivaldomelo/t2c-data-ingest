import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  AlertTriangle,
  ArrowLeft,
  Ban,
  Check,
  ClipboardCopy,
  Clock,
  Copy,
  Cpu,
  Database,
  ExternalLink,
  FileDown,
  GitBranch,
  Info,
  Play,
  Timer,
  TrendingDown,
  TrendingUp,
  User,
} from "lucide-react";

import { api } from "@/lib/api";
import { Card, PrimaryButton, SecondaryButton } from "@/components/ui";
import { Skeleton } from "@/components/ui/LoadingSkeleton";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/cn";
import { ExecutionLogViewer, type ExecLogLine } from "@/features/executions/ExecutionLogViewer";
import { ExecutionStatusBadge, ExecutionTriggerBadge } from "@/features/executions/ExecutionBadges";

interface ConnInfo {
  name: string | null;
  type: string | null;
  host: string | null;
  port: number | null;
  database: string | null;
  test_status: string | null;
}
interface IngestSummary {
  table: string | null;
  tipo: string | null;
  incr_col: string | null;
  watermark_anterior: string | null;
  watermark_novo: string | null;
  lidos: number | null;
  gravados: number | null;
  status: string | null;
}
interface Detail {
  id: number;
  target_type: string;
  execution_type: string | null;
  target_name: string | null;
  job_id: number | null;
  job_type: string | null;
  status: string;
  engine: string | null;
  trigger_type: string;
  triggered_by: string | null;
  schedule_id: number | null;
  schedule_name: string | null;
  scheduled_for: string | null;
  triggered_at: string | null;
  pipeline_id: number | null;
  pipeline_name: string | null;
  pipeline_execution_id: number | null;
  step_name: string | null;
  step_order: number | null;
  queued_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  duration_seconds: number | null;
  final_message: string | null;
  error_trace: string | null;
  source_connection: ConnInfo | null;
  target_connection: ConnInfo | null;
  ingest_summary: IngestSummary | null;
  records_read: number | null;
  records_written: number | null;
  runtime_parameters: { id: number; key: string; value: string | null }[];
  logs: ExecLogLine[];
}

const JOB_TYPE_LABEL: Record<string, string> = {
  python: "Python", spark_python: "Spark · Python", spark_sql: "Spark · SQL", spark_submit: "Spark · Submit",
};

function fmtDur(s: number | null): string {
  if (s == null) return "—";
  if (s < 60) return `${s}s`;
  return `${Math.floor(s / 60)}m ${s % 60}s`;
}
function fmtTime(t: string | null): string {
  return t ? new Date(t).toLocaleString("pt-BR") : "—";
}

export default function ExecutionDetailPage() {
  const { id } = useParams();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { can } = useAuth();
  const [copiedField, setCopiedField] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["execution", id],
    queryFn: () => api.get<Detail>(`/api/v1/executions/${id}`),
    refetchInterval: (q) =>
      ["queued", "running"].includes((q.state.data as Detail | undefined)?.status ?? "") ? 3000 : false,
  });

  const cancel = useMutation({
    mutationFn: () => api.post(`/api/v1/executions/${id}/cancel`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["execution", id] }),
  });
  const rerun = useMutation({
    mutationFn: () => api.post<{ id: number }>(`/api/v1/jobs/${data?.job_id}/run`, {}),
    onSuccess: (res) => navigate(`/executions/${res.id}`),
  });

  function flash(field: string) {
    setCopiedField(field);
    setTimeout(() => setCopiedField(null), 1500);
  }
  async function copy(text: string, field: string) {
    try {
      await navigator.clipboard.writeText(text);
      flash(field);
    } catch {
      /* ignore */
    }
  }

  if (isLoading || !data) {
    return (
      <div>
        <Skeleton className="h-24 rounded-2xl" />
        <div className="mt-6 grid grid-cols-2 gap-4 lg:grid-cols-6">
          {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-24 rounded-2xl" />)}
        </div>
        <Skeleton className="mt-6 h-[500px] rounded-2xl" />
      </div>
    );
  }

  const isError = ["failed", "timeout"].includes(data.status);
  const isRunning = ["queued", "running"].includes(data.status);
  const zeroRecords =
    data.status === "success" && (data.records_read ?? 0) === 0 && (data.records_written ?? 0) === 0;
  const kind = (data.execution_type ?? data.target_type) === "pipeline" ? "Pipeline" : "Job";
  const plainLogs = data.logs.map((l) => l.message).join("\n");

  return (
    <div className="space-y-6">
      {/* ── Header ── */}
      <Card className="p-5">
        <Link to="/executions" className="mb-3 inline-flex items-center gap-1.5 text-sm text-gray-500 transition-colors hover:text-gray-800">
          <ArrowLeft size={16} /> Voltar para Execuções
        </Link>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-2xl font-bold tracking-tight text-gray-900">{data.target_name ?? `Execução #${data.id}`}</h1>
              <ExecutionStatusBadge status={data.status} size="lg" />
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-gray-500">
              <span className="font-mono text-gray-400">#{data.id}</span>
              <Dot /> <span>{kind}</span>
              {data.job_type && (<><Dot /> <span>{JOB_TYPE_LABEL[data.job_type] ?? data.job_type}</span></>)}
              {data.engine && (<><Dot /> <span className="font-mono">{data.engine}</span></>)}
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-gray-400">
              <ExecutionTriggerBadge trigger={data.trigger_type} />
              {data.triggered_by && <span>por {data.triggered_by}</span>}
              <Dot /> <span>Iniciado em {fmtTime(data.started_at)}</span>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <IconButton onClick={() => copy(String(data.id), "id")} icon={copiedField === "id" ? <Check size={15} className="text-emerald-500" /> : <ClipboardCopy size={15} />}>Copiar ID</IconButton>
            <IconButton onClick={() => copy(plainLogs, "logs")} icon={copiedField === "logs" ? <Check size={15} className="text-emerald-500" /> : <Copy size={15} />}>Copiar logs</IconButton>
            {data.job_id && <IconButton onClick={() => navigate(`/jobs/${data.job_id}`)} icon={<ExternalLink size={15} />}>Abrir job</IconButton>}
            {data.pipeline_id && <IconButton onClick={() => navigate(`/pipelines/${data.pipeline_id}`)} icon={<GitBranch size={15} />}>Abrir pipeline</IconButton>}
            {data.pipeline_execution_id && <IconButton onClick={() => navigate(`/executions/${data.pipeline_execution_id}`)} icon={<ExternalLink size={15} />}>Execução do pipeline</IconButton>}
            {can("ingest:run") && isRunning && (
              <SecondaryButton icon={<Ban size={16} />} loading={cancel.isPending} onClick={() => cancel.mutate()}>Cancelar</SecondaryButton>
            )}
            {can("ingest:run") && data.job_id && !isRunning && (
              <PrimaryButton icon={<Play size={16} />} loading={rerun.isPending} onClick={() => rerun.mutate()}>Reexecutar</PrimaryButton>
            )}
          </div>
        </div>
      </Card>

      {/* ── Erro ── */}
      {isError && (
        <Card className="border-red-200 bg-red-50/60 p-5">
          <div className="flex items-start gap-3">
            <div className="rounded-lg bg-red-100 p-2 text-red-600"><AlertTriangle size={18} /></div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold text-red-800">Falha na execução</p>
              <p className="mt-1 text-sm text-red-700">{data.final_message ?? "A execução terminou com erro."}</p>
              {data.error_trace && (
                <pre className="mt-3 max-h-52 overflow-auto rounded-lg bg-red-100/60 p-3 font-mono text-xs text-red-800">{data.error_trace}</pre>
              )}
              <div className="mt-3 flex gap-2">
                <button onClick={() => copy(`${data.final_message ?? ""}\n${data.error_trace ?? ""}`.trim(), "err")}
                  className="inline-flex items-center gap-1.5 rounded-md border border-red-200 bg-white px-2.5 py-1 text-xs font-medium text-red-700 hover:bg-red-50">
                  {copiedField === "err" ? <Check size={13} /> : <Copy size={13} />} Copiar erro
                </button>
              </div>
            </div>
          </div>
        </Card>
      )}

      {/* ── Sucesso com zero registros ── */}
      {zeroRecords && (
        <div className="flex items-start gap-2 rounded-xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-800">
          <Info size={16} className="mt-0.5 shrink-0" />
          Execução concluída com sucesso. Nenhum novo registro foi encontrado para processar.
        </div>
      )}

      {/* ── Cards de resumo ── */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-6">
        <SummaryCard icon={<Clock size={15} />} label="Status"><ExecutionStatusBadge status={data.status} size="sm" /></SummaryCard>
        <SummaryCard icon={<Cpu size={15} />} label="Engine"><span className="font-mono text-sm text-gray-800">{data.engine ?? "—"}</span></SummaryCard>
        <SummaryCard icon={<Timer size={15} />} label="Duração"><span className="text-sm font-semibold text-gray-900">{fmtDur(data.duration_seconds)}</span></SummaryCard>
        <SummaryCard icon={<User size={15} />} label="Disparado por"><span className="text-sm text-gray-800">{data.trigger_type}</span></SummaryCard>
        <SummaryCard icon={<TrendingDown size={15} />} label="Lidos"><span className="text-sm font-semibold text-gray-900">{data.records_read ?? "—"}</span></SummaryCard>
        <SummaryCard icon={<TrendingUp size={15} />} label="Gravados"><span className="text-sm font-semibold text-gray-900">{data.records_written ?? "—"}</span></SummaryCard>
      </div>

      {/* ── Timeline + Origem/Destino ── */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <TimelineCard data={data} />
        <ConnectionsCard source={data.source_connection} target={data.target_connection} />
      </div>

      {/* ── Resumo da ingestão ── */}
      {data.ingest_summary && <IngestSummaryCard s={data.ingest_summary} />}

      {/* ── Logs ── */}
      <ExecutionLogViewer lines={data.logs} fileName={`execucao-${data.id}.log`} running={isRunning} />
    </div>
  );
}

/* ── local components ── */
function Dot() {
  return <span className="text-gray-300">·</span>;
}

function IconButton({ children, icon, onClick }: { children: React.ReactNode; icon: React.ReactNode; onClick: () => void }) {
  return (
    <button onClick={onClick} className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 text-sm font-medium text-gray-600 transition-colors hover:bg-gray-50 hover:text-gray-900">
      {icon} {children}
    </button>
  );
}

function SummaryCard({ icon, label, children }: { icon: React.ReactNode; label: string; children: React.ReactNode }) {
  return (
    <Card className="p-4">
      <div className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-gray-500">
        <span className="text-gray-400">{icon}</span>{label}
      </div>
      <div className="mt-2">{children}</div>
    </Card>
  );
}

function TimeRow({ label, value, tone = "gray" }: { label: string; value: string; tone?: "gray" | "green" | "amber" }) {
  const dot = tone === "green" ? "bg-emerald-500" : tone === "amber" ? "bg-amber-500" : "bg-gray-300";
  return (
    <div className="relative flex gap-3 pb-4 last:pb-0">
      <span className="absolute left-[5px] top-4 h-full w-px bg-gray-200 last:hidden" aria-hidden />
      <span className={cn("z-10 mt-1 h-2.5 w-2.5 shrink-0 rounded-full ring-2 ring-white", dot)} />
      <div className="flex-1">
        <p className="text-xs font-medium uppercase tracking-wide text-gray-400">{label}</p>
        <p className="text-sm text-gray-800">{value}</p>
      </div>
    </div>
  );
}

function TimelineCard({ data }: { data: Detail }) {
  const done = data.status === "success";
  return (
    <Card className="p-5">
      {data.trigger_type === "schedule" && (
        <InfoBlock title="Disparado por: Agendamento">
          <div>Agendamento: <span className="font-medium">{data.schedule_name ?? `#${data.schedule_id}`}</span></div>
          <div>Horário previsto: {fmtTime(data.scheduled_for)}</div>
          <div>Horário de disparo: {fmtTime(data.triggered_at)}</div>
        </InfoBlock>
      )}
      {data.trigger_type === "pipeline" && (data.pipeline_name || data.step_name) && (
        <InfoBlock title="Disparado por: Pipeline">
          <div>Pipeline de origem: <span className="font-medium">{data.pipeline_name ?? `#${data.pipeline_id}`}</span></div>
          {data.step_name && <div>Step do pipeline: <span className="font-medium">{data.step_name}</span></div>}
          {data.step_order != null && <div>Ordem do step: {data.step_order}</div>}
        </InfoBlock>
      )}
      <h2 className="mb-4 text-sm font-semibold text-gray-900">Linha do tempo</h2>
      <div>
        <TimeRow label="Enfileirado" value={fmtTime(data.queued_at)} tone={data.queued_at ? "green" : "gray"} />
        <TimeRow label="Início" value={fmtTime(data.started_at)} tone={data.started_at ? "green" : "gray"} />
        <TimeRow label="Fim" value={fmtTime(data.finished_at)} tone={data.finished_at ? (done ? "green" : "amber") : "gray"} />
        <TimeRow label="Duração" value={fmtDur(data.duration_seconds)} tone="gray" />
      </div>
      {data.runtime_parameters.length > 0 && (
        <div className="mt-4 border-t border-gray-100 pt-4">
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Parâmetros</h3>
          <div className="space-y-1">
            {data.runtime_parameters.map((p) => (
              <div key={p.id} className="flex justify-between gap-2 font-mono text-xs">
                <span className="text-gray-500">{p.key}</span>
                <span className="truncate text-gray-800">{p.value ?? "—"}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}

function InfoBlock({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-4 rounded-lg border border-brand-200 bg-brand-50 p-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-brand-700">{title}</p>
      <div className="mt-1 space-y-0.5 text-xs text-gray-700">{children}</div>
    </div>
  );
}

function ConnBox({ role, c }: { role: "Origem" | "Destino"; c: ConnInfo | null }) {
  return (
    <div className="rounded-xl border border-gray-100 bg-gray-50/60 p-4">
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">{role}</p>
      {!c ? (
        <p className="text-sm text-gray-400">Não identificada.</p>
      ) : (
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-gray-900">{c.name ?? "—"}</span>
            {c.type && <span className="rounded bg-gray-200/70 px-1.5 py-0.5 text-[11px] font-medium uppercase text-gray-600">{c.type}</span>}
          </div>
          <p className="break-all font-mono text-xs text-gray-500">
            {c.host ?? "—"}{c.port ? `:${c.port}` : ""}{c.database ? `/${c.database}` : ""}
          </p>
          {c.test_status && (
            <p className={cn("text-xs font-medium", c.test_status === "success" ? "text-emerald-600" : "text-red-600")}>
              Teste: {c.test_status === "success" ? "OK" : "Falhou"}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function ConnectionsCard({ source, target }: { source: ConnInfo | null; target: ConnInfo | null }) {
  return (
    <Card className="p-5">
      <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold text-gray-900">
        <Database size={15} className="text-brand-500" /> Origem e destino
      </h2>
      {!source && !target ? (
        <p className="text-sm text-gray-400">Sem metadados de conexão para esta execução.</p>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <ConnBox role="Origem" c={source} />
          <ConnBox role="Destino" c={target} />
        </div>
      )}
    </Card>
  );
}

function IngestField({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-gray-400">{label}</dt>
      <dd className="mt-0.5 text-sm text-gray-800">{value}</dd>
    </div>
  );
}

function IngestSummaryCard({ s }: { s: IngestSummary }) {
  const statusOk = (s.status ?? "").toUpperCase().startsWith("SUC");
  const watermark = s.watermark_novo ?? "Nenhum novo registro processado (watermark mantido)";
  return (
    <Card className="p-5">
      <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold text-gray-900">
        <FileDown size={15} className="text-brand-500" /> Resumo da ingestão
      </h2>
      <dl className="grid grid-cols-2 gap-x-6 gap-y-4 md:grid-cols-4">
        <IngestField label="Tabela" value={<span className="font-mono text-xs">{s.table ?? "—"}</span>} />
        <IngestField label="Tipo de ingestão" value={s.tipo ?? "—"} />
        <IngestField label="Coluna incremental" value={<span className="font-mono text-xs">{s.incr_col ?? "—"}</span>} />
        <IngestField label="Status" value={
          s.status ? (
            <span className={cn("inline-flex rounded-full px-2 py-0.5 text-xs font-medium",
              statusOk ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700")}>{s.status}</span>
          ) : "—"
        } />
        <IngestField label="Watermark anterior" value={<span className="font-mono text-xs">{s.watermark_anterior ?? "—"}</span>} />
        <IngestField label="Watermark novo" value={<span className={cn("text-xs", s.watermark_novo ? "font-mono" : "text-gray-500")}>{watermark}</span>} />
        <IngestField label="Registros lidos" value={<span className="font-semibold">{s.lidos ?? "—"}</span>} />
        <IngestField label="Registros gravados" value={<span className="font-semibold">{s.gravados ?? "—"}</span>} />
      </dl>
    </Card>
  );
}
