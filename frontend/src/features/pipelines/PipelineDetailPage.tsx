import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, GitBranch, ListChecks, PlayCircle, Settings2, Workflow } from "lucide-react";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/cn";
import { Card, EmptyState, PrimaryButton, StatusBadge } from "@/components/ui";
import { Skeleton } from "@/components/ui/LoadingSkeleton";
import { PipelineBuilderModal } from "@/features/pipelines/PipelineBuilderModal";
import { PipelineExecutionsTab } from "@/features/pipelines/PipelineExecutionsTab";
import type { PipelineDetail } from "@/features/pipelines/types";
import { fmtDate, fmtDuration } from "@/features/pipelines/types";

type Tab = "overview" | "builder" | "executions" | "logs" | "settings";
const TABS: { key: Tab; label: string; icon: typeof Workflow }[] = [
  { key: "overview", label: "Visão geral", icon: ListChecks },
  { key: "builder", label: "Builder", icon: GitBranch },
  { key: "executions", label: "Execuções", icon: PlayCircle },
  { key: "logs", label: "Logs", icon: PlayCircle },
  { key: "settings", label: "Configurações", icon: Settings2 },
];

export default function PipelineDetailPage() {
  const { id } = useParams();
  const pid = Number(id);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { can } = useAuth();
  const [tab, setTab] = useState<Tab>("overview");
  const [builderOpen, setBuilderOpen] = useState(false);

  const { data: p, isLoading, error } = useQuery({
    queryKey: ["pipeline", pid],
    queryFn: () => api.get<PipelineDetail>(`/api/v1/pipelines/${pid}`),
  });

  const run = useMutation({
    mutationFn: () => api.post(`/api/v1/pipelines/${pid}/run`, {}),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["pipeline-executions", pid] }); setTab("executions"); },
    onError: (e) => alert(e instanceof Error ? e.message : "Falha ao executar (valide o pipeline)."),
  });

  if (isLoading) return <div><Skeleton className="h-8 w-64" /><Skeleton className="mt-6 h-40 rounded-2xl" /></div>;
  if (error || !p) return <EmptyState title="Pipeline não encontrado" description="O pipeline solicitado não existe." />;

  const canRun = can("ingest:pipelines:run");

  return (
    <div>
      <div className="mb-6">
        <button onClick={() => navigate("/pipelines")} className="mb-4 inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-800">
          <ArrowLeft size={16} /> Voltar para Pipelines
        </button>
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold tracking-tight text-gray-900">{p.name}</h1>
              <StatusBadge status={p.is_active ? "active" : "inactive"} />
            </div>
            {p.description && <p className="mt-1 text-sm text-gray-500">{p.description}</p>}
          </div>
          <div className="flex items-center gap-2">
            <PrimaryButton icon={<GitBranch size={16} />} onClick={() => setBuilderOpen(true)}>Abrir Builder</PrimaryButton>
            {canRun && <PrimaryButton className="bg-gray-800 hover:bg-gray-900" icon={<PlayCircle size={16} />} loading={run.isPending} disabled={!p.is_active} onClick={() => run.mutate()}>Executar</PrimaryButton>}
          </div>
        </div>
      </div>

      {builderOpen && <PipelineBuilderModal pipeline={p} onClose={() => { setBuilderOpen(false); qc.invalidateQueries({ queryKey: ["pipeline", pid] }); }} />}

      <div className="mb-6 border-b border-gray-200">
        <nav className="-mb-px flex gap-1">
          {TABS.map(({ key, label, icon: Icon }) => (
            <button key={key} onClick={() => setTab(key)}
              className={cn("inline-flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors",
                tab === key ? "border-brand-500 text-brand-600" : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700")}>
              <Icon size={16} /> {label}
            </button>
          ))}
        </nav>
      </div>

      {tab === "overview" && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <Card className="p-5 lg:col-span-2">
            <h2 className="mb-4 text-sm font-semibold text-gray-900">Informações</h2>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-4 text-sm">
              <Info label="Grupo" value={p.group_name ?? "—"} />
              <Info label="Ativo" value={p.is_active ? "Sim" : "Não"} />
              <Info label="Total de jobs" value={String(p.steps_count)} />
              <Info label="Total de dependências" value={String(p.dependencies_count)} />
              <Info label="Criado por" value={p.created_by ?? "—"} />
              <Info label="Atualizado em" value={fmtDate(p.updated_at)} />
            </dl>
          </Card>
          <Card className="p-5">
            <h2 className="mb-4 text-sm font-semibold text-gray-900">Execuções</h2>
            <dl className="space-y-4 text-sm">
              <Info label="Total" value={String(p.executions_total)} />
              <Info label="Última" value={p.last_execution_id ? `#${p.last_execution_id} · ${fmtDate(p.last_finished_at)}` : "—"} />
              <div><dt className="text-xs font-medium uppercase tracking-wide text-gray-400">Último status</dt><dd className="mt-0.5">{p.last_status ? <StatusBadge status={p.last_status === "partial_success" ? "timeout" : p.last_status} label={p.last_status} /> : "—"}</dd></div>
              <Info label="Duração média" value={fmtDuration(p.avg_duration_seconds)} />
            </dl>
          </Card>
        </div>
      )}

      {tab === "builder" && (
        <Card className="flex flex-col items-center gap-3 p-10 text-center">
          <GitBranch size={28} className="text-brand-500" />
          <p className="text-sm text-gray-600">Monte a DAG do pipeline no editor visual (modal amplo, estilo Airflow).</p>
          <PrimaryButton icon={<GitBranch size={16} />} onClick={() => setBuilderOpen(true)}>Abrir Builder</PrimaryButton>
        </Card>
      )}
      {tab === "executions" && <PipelineExecutionsTab pipelineId={pid} />}
      {tab === "logs" && (
        <Card className="p-5">
          <p className="text-sm text-gray-600">Os logs detalhados ficam por execução/step. Abra a aba <b>Execuções</b>, clique numa execução e depois em <b>ver logs</b> do step para abrir os logs do job correspondente.</p>
        </Card>
      )}
      {tab === "settings" && <PipelineSettings pipeline={p} onSaved={() => qc.invalidateQueries({ queryKey: ["pipeline", pid] })} canWrite={can("ingest:pipelines:write")} />}
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return <div><dt className="text-xs font-medium uppercase tracking-wide text-gray-400">{label}</dt><dd className="mt-0.5 text-gray-800">{value}</dd></div>;
}

function PipelineSettings({ pipeline, onSaved, canWrite }: { pipeline: PipelineDetail; onSaved: () => void; canWrite: boolean }) {
  const [name, setName] = useState(pipeline.name);
  const [description, setDescription] = useState(pipeline.description ?? "");
  const [group, setGroup] = useState(pipeline.group_name ?? "");
  const [active, setActive] = useState(pipeline.is_active);
  const save = useMutation({
    mutationFn: () => api.put(`/api/v1/pipelines/${pipeline.id}`, { name, description: description || null, group_name: group || null, is_active: active }),
    onSuccess: onSaved,
  });
  const inp = "mt-1.5 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-brand-400 focus:outline-none";
  return (
    <Card className="max-w-xl p-5">
      <div className="space-y-4">
        <div><label className="text-sm font-medium text-gray-700">Nome</label><input className={inp} value={name} onChange={(e) => setName(e.target.value)} disabled={!canWrite} /></div>
        <div><label className="text-sm font-medium text-gray-700">Descrição</label><input className={inp} value={description} onChange={(e) => setDescription(e.target.value)} disabled={!canWrite} /></div>
        <div><label className="text-sm font-medium text-gray-700">Grupo</label><input className={inp} value={group} onChange={(e) => setGroup(e.target.value)} disabled={!canWrite} /></div>
        <label className="flex items-center gap-2 text-sm text-gray-700"><input type="checkbox" className="h-4 w-4 rounded border-gray-300 text-brand-500" checked={active} onChange={(e) => setActive(e.target.checked)} disabled={!canWrite} /> Ativo</label>
        {canWrite && <div className="flex justify-end"><PrimaryButton loading={save.isPending} onClick={() => save.mutate()}>Salvar</PrimaryButton></div>}
      </div>
    </Card>
  );
}
