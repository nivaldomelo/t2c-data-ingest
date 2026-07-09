import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";

import { api, ApiError, type Page } from "@/lib/api";
import { Modal, PrimaryButton, SecondaryButton } from "@/components/ui";
import { TagInput } from "@/features/tags/TagInput";
import { useAuth } from "@/lib/auth";
import type { JobDetail } from "@/features/jobs/types";
import { JOB_TYPE_LABEL } from "@/features/jobs/types";

const JOB_TYPES = ["python", "spark_python", "spark_sql", "spark_submit"] as const;

interface ConnectionLite {
  id: number;
  name: string;
  connection_type: string;
}

const inputCls =
  "w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800 outline-none transition-colors focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20";
const labelCls = "mb-1 block text-xs font-medium text-gray-600";

export function JobEditModal({
  job, open, onClose,
}: {
  job: JobDetail; open: boolean; onClose: () => void;
}) {
  const qc = useQueryClient();
  const { can } = useAuth();
  const canTags = can("ingest:jobs:tags:write");

  const [name, setName] = useState(job.name);
  const [description, setDescription] = useState(job.description ?? "");
  const [type, setType] = useState(job.type);
  const [engine, setEngine] = useState(job.engine ?? "");
  const [scriptPath, setScriptPath] = useState(job.script_path ?? "");
  const [mainClass, setMainClass] = useState(job.main_class ?? "");
  const [clusterId, setClusterId] = useState<string>(job.cluster_id?.toString() ?? "");
  const [singleConn, setSingleConn] = useState<string>(job.connection_id?.toString() ?? "");
  const [sourceConn, setSourceConn] = useState<string>(job.source_connection_id?.toString() ?? "");
  const [targetConn, setTargetConn] = useState<string>(job.target_connection_id?.toString() ?? "");
  const [args, setArgs] = useState<string>(((job.arguments ?? []) as unknown[]).map(String).join(" "));
  const [defaultParams, setDefaultParams] = useState(
    job.default_parameters ? JSON.stringify(job.default_parameters, null, 2) : ""
  );
  const [timeout, setTimeoutS] = useState<string>(job.timeout_seconds?.toString() ?? "");
  const [retry, setRetry] = useState<string>(String(job.retry_count ?? 0));
  const [isActive, setIsActive] = useState(job.is_active);
  const [tags, setTags] = useState<string[]>((job.tags ?? []).map((t) => t.name));
  const [error, setError] = useState<string | null>(null);

  const { data: connections } = useQuery({
    queryKey: ["connections-lite"],
    queryFn: () => api.get<Page<ConnectionLite>>("/api/v1/connections?page=1&page_size=200"),
    enabled: open,
  });
  const connOptions = connections?.items ?? [];

  const paramsError = useMemo(() => {
    if (!defaultParams.trim()) return null;
    try {
      const v = JSON.parse(defaultParams);
      if (typeof v !== "object" || Array.isArray(v)) return "Deve ser um objeto JSON.";
      return null;
    } catch {
      return "JSON inválido.";
    }
  }, [defaultParams]);

  const save = useMutation({
    mutationFn: async () => {
      const body: Record<string, unknown> = {
        name: name.trim(),
        description: description.trim() || null,
        type,
        engine: engine.trim() || null,
        script_path: scriptPath.trim() || null,
        main_class: mainClass.trim() || null,
        cluster_id: clusterId ? Number(clusterId) : null,
        connection_id: singleConn ? Number(singleConn) : null,
        source_connection_id: sourceConn ? Number(sourceConn) : null,
        target_connection_id: targetConn ? Number(targetConn) : null,
        arguments: args.trim() ? args.trim().split(/\s+/) : null,
        default_parameters: defaultParams.trim() ? JSON.parse(defaultParams) : null,
        timeout_seconds: timeout.trim() ? Number(timeout) : null,
        retry_count: retry.trim() ? Number(retry) : 0,
        is_active: isActive,
      };
      await api.patch(`/api/v1/jobs/${job.id}`, body);
      if (canTags) await api.put(`/api/v1/jobs/${job.id}/tags`, { tags });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["job", job.id] });
      qc.invalidateQueries({ queryKey: ["jobs"] });
      onClose();
    },
    onError: (err) => {
      setError(err instanceof ApiError ? err.message : "Falha ao salvar o job.");
    },
  });

  function submit() {
    setError(null);
    if (!name.trim()) return setError("O nome do job é obrigatório.");
    if (!JOB_TYPES.includes(type as (typeof JOB_TYPES)[number])) return setError("Tipo de job inválido.");
    if (paramsError) return setError(`Parâmetros padrão: ${paramsError}`);
    save.mutate();
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Editar job"
      description="Atualize os dados principais do job."
      width="max-w-2xl"
      footer={
        <>
          <SecondaryButton onClick={onClose}>Cancelar</SecondaryButton>
          <PrimaryButton loading={save.isPending} onClick={submit}>Salvar alterações</PrimaryButton>
        </>
      }
    >
      {error && (
        <div className="mb-4 flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-3.5 py-2 text-sm text-red-700">
          <AlertTriangle size={16} className="mt-0.5 shrink-0" /> {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <label className={labelCls}>Nome *</label>
          <input className={inputCls} value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div className="sm:col-span-2">
          <label className={labelCls}>Descrição</label>
          <textarea className={inputCls} rows={2} value={description} onChange={(e) => setDescription(e.target.value)} />
        </div>
        <div>
          <label className={labelCls}>Tipo *</label>
          <select className={inputCls} value={type} onChange={(e) => setType(e.target.value)}>
            {JOB_TYPES.map((t) => (
              <option key={t} value={t}>{JOB_TYPE_LABEL[t] ?? t}</option>
            ))}
          </select>
        </div>
        <div>
          <label className={labelCls}>Engine</label>
          <input className={inputCls} value={engine} onChange={(e) => setEngine(e.target.value)} placeholder="python_worker / spark_cluster" />
        </div>
        <div className="sm:col-span-2">
          <label className={labelCls}>Script path</label>
          <input className={`${inputCls} font-mono text-xs`} value={scriptPath} onChange={(e) => setScriptPath(e.target.value)} placeholder="/opt/t2c/python_jobs/…/main.py" />
          <p className="mt-1 text-xs text-gray-400">Deve estar dentro de um diretório permitido (spark/jobs, python_jobs…).</p>
        </div>
        <div>
          <label className={labelCls}>Classe principal</label>
          <input className={`${inputCls} font-mono text-xs`} value={mainClass} onChange={(e) => setMainClass(e.target.value)} placeholder="com.exemplo.Main" />
        </div>
        <div>
          <label className={labelCls}>Cluster ID</label>
          <input className={inputCls} type="number" min={0} value={clusterId} onChange={(e) => setClusterId(e.target.value)} placeholder="—" />
        </div>
        <div>
          <label className={labelCls}>Conexão única</label>
          <select className={inputCls} value={singleConn} onChange={(e) => setSingleConn(e.target.value)}>
            <option value="">—</option>
            {connOptions.map((c) => <option key={c.id} value={c.id}>{c.name} ({c.connection_type})</option>)}
          </select>
        </div>
        <div>
          <label className={labelCls}>Conexão origem</label>
          <select className={inputCls} value={sourceConn} onChange={(e) => setSourceConn(e.target.value)}>
            <option value="">—</option>
            {connOptions.map((c) => <option key={c.id} value={c.id}>{c.name} ({c.connection_type})</option>)}
          </select>
        </div>
        <div>
          <label className={labelCls}>Conexão destino</label>
          <select className={inputCls} value={targetConn} onChange={(e) => setTargetConn(e.target.value)}>
            <option value="">—</option>
            {connOptions.map((c) => <option key={c.id} value={c.id}>{c.name} ({c.connection_type})</option>)}
          </select>
        </div>
        <div>
          <label className={labelCls}>Timeout (s)</label>
          <input className={inputCls} type="number" min={0} value={timeout} onChange={(e) => setTimeoutS(e.target.value)} />
        </div>
        <div>
          <label className={labelCls}>Retry</label>
          <input className={inputCls} type="number" min={0} value={retry} onChange={(e) => setRetry(e.target.value)} />
        </div>
        <div className="sm:col-span-2">
          <label className={labelCls}>Argumentos</label>
          <textarea className={`${inputCls} font-mono text-xs`} rows={2} value={args} onChange={(e) => setArgs(e.target.value)} placeholder="--source-connection mysql_1 --target-table payments" />
          <p className="mt-1 text-xs text-gray-400">Separados por espaço. Ex.: <code>--flag valor</code>.</p>
        </div>
        <div className="sm:col-span-2">
          <label className={labelCls}>Parâmetros padrão (JSON)</label>
          <textarea className={`${inputCls} font-mono text-xs`} rows={3} value={defaultParams} onChange={(e) => setDefaultParams(e.target.value)} placeholder='{ "chave": "valor" }' />
          {paramsError && <p className="mt-1 text-xs text-red-500">{paramsError}</p>}
        </div>
        <div className="sm:col-span-2">
          <label className={labelCls}>Tags</label>
          <TagInput value={tags} onChange={setTags} allowCreate={canTags} disabled={!canTags} placeholder="Adicionar tag e Enter…" />
        </div>
        <div className="sm:col-span-2">
          <label className="inline-flex items-center gap-2 text-sm text-gray-700">
            <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} className="h-4 w-4 rounded border-gray-300 text-brand-500 focus:ring-brand-500" />
            Job ativo
          </label>
        </div>
      </div>
    </Modal>
  );
}
