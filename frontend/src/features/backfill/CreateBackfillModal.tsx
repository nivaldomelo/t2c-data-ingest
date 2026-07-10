import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Boxes, Database, GitBranch, RotateCcw, Table2 } from "lucide-react";

import { api, ApiError, type Page } from "@/lib/api";
import { Modal, PrimaryButton, SecondaryButton } from "@/components/ui";
import { cn } from "@/lib/cn";
import { useAuth } from "@/lib/auth";

type Kind = "job" | "pipeline" | "control_group" | "control_table";

const KINDS: { value: Kind; label: string; desc: string; icon: typeof Boxes }[] = [
  { value: "job", label: "Job", desc: "Reprocessar um job específico", icon: Boxes },
  { value: "pipeline", label: "Pipeline", desc: "Reexecutar pipeline (opcional: a partir de um step)", icon: GitBranch },
  { value: "control_group", label: "Grupo de controle", desc: "Reprocessar todos os jobs de um grupo", icon: Database },
  { value: "control_table", label: "Tabela de controle", desc: "Reprocessar os jobs de uma tabela", icon: Table2 },
];

const inputCls = "w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800 outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20";
const labelCls = "mb-1 block text-xs font-medium text-gray-600";

interface Opt { id: number; name: string }

export function CreateBackfillModal({ open, onClose, preset }: {
  open: boolean; onClose: () => void; preset?: { kind: Kind; job_id?: number; pipeline_id?: number; table_name?: string; control_group?: string };
}) {
  const qc = useQueryClient();
  const { can } = useAuth();
  const canWatermark = can("ingest:backfill:watermark");

  const [kind, setKind] = useState<Kind>(preset?.kind ?? "job");
  const [jobId, setJobId] = useState<string>(preset?.job_id?.toString() ?? "");
  const [pipelineId, setPipelineId] = useState<string>(preset?.pipeline_id?.toString() ?? "");
  const [fromStepId, setFromStepId] = useState<string>("");
  const [controlGroup, setControlGroup] = useState(preset?.control_group ?? "");
  const [tableName, setTableName] = useState(preset?.table_name ?? "");
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const [resetWatermark, setResetWatermark] = useState(false);
  const [watermarkValue, setWatermarkValue] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open && preset) {
      setKind(preset.kind); setJobId(preset.job_id?.toString() ?? ""); setPipelineId(preset.pipeline_id?.toString() ?? "");
      setTableName(preset.table_name ?? ""); setControlGroup(preset.control_group ?? "");
    }
  }, [open, preset]);

  const { data: jobs } = useQuery({
    queryKey: ["jobs-lite-backfill"], enabled: open && kind === "job",
    queryFn: () => api.get<Page<Opt>>("/api/v1/jobs?page=1&page_size=300"),
  });
  const { data: pipelines } = useQuery({
    queryKey: ["pipelines-lite-backfill"], enabled: open && kind === "pipeline",
    queryFn: () => api.get<Page<Opt>>("/api/v1/pipelines?page=1&page_size=300"),
  });
  const { data: steps } = useQuery({
    queryKey: ["pipeline-steps", pipelineId], enabled: open && kind === "pipeline" && !!pipelineId,
    queryFn: () => api.get<{ id: number; label: string; order_index: number }[]>(`/api/v1/pipelines/${pipelineId}/steps`),
  });

  const isControl = kind === "control_group" || kind === "control_table";

  const create = useMutation({
    mutationFn: () => api.post("/api/v1/backfills", {
      kind,
      job_id: kind === "job" && jobId ? Number(jobId) : null,
      pipeline_id: kind === "pipeline" && pipelineId ? Number(pipelineId) : null,
      from_step_id: kind === "pipeline" && fromStepId ? Number(fromStepId) : null,
      control_group: kind === "control_group" ? controlGroup.trim() || null : null,
      table_name: kind === "control_table" ? tableName.trim() || null : null,
      period_start: periodStart || null,
      period_end: periodEnd || null,
      reset_watermark: isControl && canWatermark ? resetWatermark : false,
      watermark_value: watermarkValue.trim() || null,
      reason: reason.trim() || null,
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["backfills"] }); close(); },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Falha ao criar reprocessamento."),
  });

  function close() {
    setError(null); setFromStepId(""); setPeriodStart(""); setPeriodEnd(""); setResetWatermark(false);
    setWatermarkValue(""); setReason("");
    onClose();
  }
  function submit() {
    setError(null);
    if (kind === "job" && !jobId) return setError("Selecione o job.");
    if (kind === "pipeline" && !pipelineId) return setError("Selecione o pipeline.");
    if (kind === "control_group" && !controlGroup.trim()) return setError("Informe o grupo.");
    if (kind === "control_table" && !tableName.trim()) return setError("Informe a tabela.");
    create.mutate();
  }

  const periodValid = useMemo(() => !periodStart || !periodEnd || periodStart <= periodEnd, [periodStart, periodEnd]);

  return (
    <Modal open={open} onClose={close} title="Novo reprocessamento"
      description="Reprocesse um job, pipeline, grupo ou tabela — de forma controlada e rastreável."
      width="max-w-2xl"
      footer={<>
        <SecondaryButton onClick={close}>Cancelar</SecondaryButton>
        <PrimaryButton icon={<RotateCcw size={16} />} loading={create.isPending} disabled={!periodValid} onClick={submit}>Reprocessar</PrimaryButton>
      </>}>
      {error && (
        <div className="mb-4 flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-3.5 py-2 text-sm text-red-700">
          <AlertTriangle size={16} className="mt-0.5 shrink-0" /> {error}
        </div>
      )}

      <p className="mb-2 text-xs font-medium text-gray-600">O que reprocessar?</p>
      <div className="mb-5 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {KINDS.map((k) => {
          const Icon = k.icon;
          return (
            <button key={k.value} onClick={() => setKind(k.value)}
              className={cn("rounded-xl border p-3 text-left transition-colors", kind === k.value ? "border-brand-500 bg-brand-50" : "border-gray-200 bg-white hover:border-gray-300")}>
              <Icon size={16} className={kind === k.value ? "text-brand-600" : "text-gray-400"} />
              <p className="mt-1.5 text-sm font-semibold text-gray-900">{k.label}</p>
              <p className="mt-0.5 text-[11px] leading-tight text-gray-500">{k.desc}</p>
            </button>
          );
        })}
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {kind === "job" && (
          <div className="sm:col-span-2">
            <label className={labelCls}>Job *</label>
            <select className={inputCls} value={jobId} onChange={(e) => setJobId(e.target.value)}>
              <option value="">Selecione…</option>
              {(jobs?.items ?? []).map((j) => <option key={j.id} value={j.id}>{j.name}</option>)}
            </select>
          </div>
        )}
        {kind === "pipeline" && (
          <>
            <div>
              <label className={labelCls}>Pipeline *</label>
              <select className={inputCls} value={pipelineId} onChange={(e) => { setPipelineId(e.target.value); setFromStepId(""); }}>
                <option value="">Selecione…</option>
                {(pipelines?.items ?? []).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </div>
            <div>
              <label className={labelCls}>A partir do step (opcional)</label>
              <select className={inputCls} value={fromStepId} onChange={(e) => setFromStepId(e.target.value)} disabled={!pipelineId}>
                <option value="">Pipeline inteiro</option>
                {(steps ?? []).map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
              </select>
            </div>
          </>
        )}
        {kind === "control_group" && (
          <div className="sm:col-span-2">
            <label className={labelCls}>Grupo *</label>
            <input className={inputCls} value={controlGroup} onChange={(e) => setControlGroup(e.target.value)} placeholder="ex.: massa_teste" />
          </div>
        )}
        {kind === "control_table" && (
          <div className="sm:col-span-2">
            <label className={labelCls}>Tabela *</label>
            <input className={`${inputCls} font-mono text-xs`} value={tableName} onChange={(e) => setTableName(e.target.value)} placeholder="ex.: massa_teste.clientes" />
          </div>
        )}

        <div>
          <label className={labelCls}>Período — início (opcional)</label>
          <input type="date" className={inputCls} value={periodStart} onChange={(e) => setPeriodStart(e.target.value)} />
        </div>
        <div>
          <label className={labelCls}>Período — fim (opcional)</label>
          <input type="date" className={inputCls} value={periodEnd} onChange={(e) => setPeriodEnd(e.target.value)} />
        </div>
        {!periodValid && <p className="sm:col-span-2 -mt-2 text-xs text-red-500">A data inicial deve ser anterior à final.</p>}

        {isControl && canWatermark && (
          <div className="sm:col-span-2 rounded-lg border border-amber-200 bg-amber-50/60 p-3">
            <label className="flex items-center gap-2 text-sm text-gray-700">
              <input type="checkbox" checked={resetWatermark} onChange={(e) => setResetWatermark(e.target.checked)} className="h-4 w-4 rounded border-gray-300 text-brand-500 focus:ring-brand-500" />
              Redefinir watermark das tabelas do controle
            </label>
            {resetWatermark && (
              <>
                <input className={`${inputCls} mt-2 font-mono text-xs`} value={watermarkValue} onChange={(e) => setWatermarkValue(e.target.value)}
                  placeholder="Novo watermark (ISO). Vazio = do zero / início do período." />
                <p className="mt-1 text-xs text-amber-700">Altera o estado incremental — use com cuidado. Ação auditada.</p>
              </>
            )}
          </div>
        )}

        <div className="sm:col-span-2">
          <label className={labelCls}>Motivo (opcional)</label>
          <input className={inputCls} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="ex.: correção de carga, dados faltando…" />
        </div>
      </div>
    </Modal>
  );
}
