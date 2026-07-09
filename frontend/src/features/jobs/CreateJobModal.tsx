import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { AlertTriangle, ArrowLeft, Code2, Flame, Plus, Trash2, Zap } from "lucide-react";

import { api, ApiError, type Page } from "@/lib/api";
import { Modal, PrimaryButton, SecondaryButton } from "@/components/ui";
import { TagInput } from "@/features/tags/TagInput";
import { cn } from "@/lib/cn";

type Engine = "spark_cluster" | "python_worker";

const TYPES: Record<Engine, { value: string; label: string; desc: string }[]> = {
  spark_cluster: [
    { value: "spark_python", label: "Spark Python", desc: "Executa scripts PySpark .py" },
    { value: "spark_sql", label: "Spark SQL", desc: "Executa arquivos ou comandos SQL no Spark" },
    { value: "spark_submit", label: "Spark Submit", desc: "Aplicação Spark com parâmetros avançados" },
  ],
  python_worker: [
    { value: "python", label: "Python", desc: "Executa scripts Python no worker da aplicação" },
  ],
};

interface ConnectionLite { id: number; name: string; connection_type: string; last_test_status?: string }

const inputCls =
  "w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800 outline-none transition-colors focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20";
const labelCls = "mb-1 block text-xs font-medium text-gray-600";

export function CreateJobModal({ open, onClose, canRun }: { open: boolean; onClose: () => void; canRun: boolean }) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [engine, setEngine] = useState<Engine | null>(null);
  const [type, setType] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [createWorkspace, setCreateWorkspace] = useState(true);
  const [scriptPath, setScriptPath] = useState("");
  const [mainClass, setMainClass] = useState("");
  const [clusterId, setClusterId] = useState("");
  const [singleConn, setSingleConn] = useState("");
  const [sourceConn, setSourceConn] = useState("");
  const [targetConn, setTargetConn] = useState("");
  const [args, setArgs] = useState<{ key: string; value: string }[]>([]);
  const [defaultParams, setDefaultParams] = useState("");
  const [timeout, setTimeoutS] = useState("");
  const [retry, setRetry] = useState("0");
  const [active, setActive] = useState(true);
  const [tags, setTags] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const { data: connections } = useQuery({
    queryKey: ["connections-lite"],
    queryFn: () => api.get<Page<ConnectionLite>>("/api/v1/connections?page=1&page_size=200"),
    enabled: open,
  });
  const conns = connections?.items ?? [];

  const argString = useMemo(
    () => args.filter((a) => a.key.trim()).map((a) => (a.value.trim() ? `--${a.key.trim()} ${a.value.trim()}` : `--${a.key.trim()}`)).join(" "),
    [args]
  );
  const paramsError = useMemo(() => {
    if (!defaultParams.trim()) return null;
    try { const v = JSON.parse(defaultParams); if (typeof v !== "object" || Array.isArray(v)) return "Deve ser um objeto JSON."; return null; }
    catch { return "JSON inválido."; }
  }, [defaultParams]);

  function reset() {
    setEngine(null); setType(""); setName(""); setDescription(""); setCreateWorkspace(true);
    setScriptPath(""); setMainClass(""); setClusterId(""); setSingleConn(""); setSourceConn("");
    setTargetConn(""); setArgs([]); setDefaultParams(""); setTimeoutS(""); setRetry("0");
    setActive(true); setTags([]); setError(null);
  }
  function close() { reset(); onClose(); }

  const create = useMutation({
    mutationFn: () => {
      const argTokens = args.filter((a) => a.key.trim()).flatMap((a) => (a.value.trim() ? [`--${a.key.trim()}`, a.value.trim()] : [`--${a.key.trim()}`]));
      return api.post<{ id: number }>("/api/v1/jobs", {
        name: name.trim(),
        description: description.trim() || null,
        engine,
        type,
        create_workspace: createWorkspace,
        script_path: createWorkspace ? null : (scriptPath.trim() || null),
        main_class: mainClass.trim() || null,
        cluster_id: clusterId ? Number(clusterId) : null,
        connection_id: singleConn ? Number(singleConn) : null,
        source_connection_id: sourceConn ? Number(sourceConn) : null,
        target_connection_id: targetConn ? Number(targetConn) : null,
        arguments: argTokens.length ? argTokens : null,
        default_parameters: defaultParams.trim() ? JSON.parse(defaultParams) : null,
        timeout_seconds: timeout.trim() ? Number(timeout) : null,
        retry_count: retry.trim() ? Number(retry) : 0,
        is_active: active,
        tags,
      });
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Falha ao criar o job."),
  });

  async function submit(after: "list" | "code" | "run") {
    setError(null);
    if (!name.trim()) return setError("O nome do job é obrigatório.");
    if (!type) return setError("Selecione o tipo do job.");
    if (paramsError) return setError(`Parâmetros padrão: ${paramsError}`);
    if (!createWorkspace && !scriptPath.trim()) return setError("Informe o script path ou marque 'Criar workspace automaticamente'.");
    try {
      const job = await create.mutateAsync();
      qc.invalidateQueries({ queryKey: ["jobs"] });
      close();
      if (after === "code") navigate(`/jobs/${job.id}`, { state: { openCode: true } });
      else if (after === "run") { try { await api.post(`/api/v1/jobs/${job.id}/run`, {}); } catch { /* */ } navigate(`/jobs/${job.id}`); }
      else navigate(`/jobs/${job.id}`);
    } catch { /* handled in onError */ }
  }

  const footer = engine && (
    <>
      <SecondaryButton onClick={close}>Cancelar</SecondaryButton>
      <SecondaryButton loading={create.isPending} onClick={() => submit("code")}>Criar e abrir código</SecondaryButton>
      {canRun && <SecondaryButton loading={create.isPending} onClick={() => submit("run")}>Criar e executar</SecondaryButton>}
      <PrimaryButton loading={create.isPending} onClick={() => submit("list")}>Criar job</PrimaryButton>
    </>
  );

  return (
    <Modal
      open={open} onClose={close} title="Criar novo job"
      description="Cadastre um job Spark ou Python para execução manual, agendada ou em pipelines."
      width="max-w-3xl" footer={footer}
    >
      {error && (
        <div className="mb-4 flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-3.5 py-2 text-sm text-red-700">
          <AlertTriangle size={16} className="mt-0.5 shrink-0" /> {error}
        </div>
      )}

      {!engine ? (
        <div>
          <p className="mb-3 text-sm font-medium text-gray-700">Escolha a engine de execução</p>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <EngineCard icon={<Flame size={22} />} title="Spark" onClick={() => { setEngine("spark_cluster"); setType("spark_python"); }}
              desc="Jobs distribuídos com PySpark, Spark SQL ou spark-submit. Ideal para grandes volumes e processamento em cluster." />
            <EngineCard icon={<Code2 size={22} />} title="Python" onClick={() => { setEngine("python_worker"); setType("python"); }}
              desc="Scripts Python simples, automações, validações e integrações. Ideal para tarefas leves fora do cluster Spark." />
          </div>
        </div>
      ) : (
        <div className="space-y-5">
          <button onClick={() => setEngine(null)} className="inline-flex items-center gap-1.5 text-xs font-medium text-gray-500 hover:text-gray-800">
            <ArrowLeft size={14} /> Trocar engine ({engine === "spark_cluster" ? "Spark" : "Python"})
          </button>

          {/* tipo */}
          <div>
            <label className={labelCls}>Tipo do job *</label>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
              {TYPES[engine].map((t) => (
                <button key={t.value} onClick={() => setType(t.value)}
                  className={cn("rounded-xl border p-3 text-left transition-colors", type === t.value ? "border-brand-500 bg-brand-50" : "border-gray-200 bg-white hover:border-gray-300")}>
                  <p className="text-sm font-semibold text-gray-900">{t.label}</p>
                  <p className="mt-0.5 text-xs text-gray-500">{t.desc}</p>
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <label className={labelCls}>Nome *</label>
              <input className={`${inputCls} font-mono`} value={name} onChange={(e) => setName(e.target.value)} placeholder="ex.: postgres_to_mysql_massa_teste_clientes" autoFocus />
              <p className="mt-1 text-xs text-gray-400">Recomendado: minúsculas, números e underline.</p>
            </div>
            <div className="sm:col-span-2">
              <label className={labelCls}>Descrição</label>
              <textarea className={inputCls} rows={2} value={description} onChange={(e) => setDescription(e.target.value)} />
            </div>

            <div className="sm:col-span-2 rounded-lg border border-gray-100 bg-gray-50/60 p-3">
              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input type="checkbox" checked={createWorkspace} onChange={(e) => setCreateWorkspace(e.target.checked)} className="h-4 w-4 rounded border-gray-300 text-brand-500 focus:ring-brand-500" />
                Criar workspace automaticamente (gera <code className="mx-1 rounded bg-white px-1 text-xs">main{engine === "spark_cluster" && type === "spark_sql" ? ".sql" : ".py"}</code> versionado)
              </label>
              {!createWorkspace && (
                <input className={`${inputCls} mt-2 font-mono text-xs`} value={scriptPath} onChange={(e) => setScriptPath(e.target.value)}
                  placeholder={engine === "spark_cluster" ? "/opt/t2c/spark/jobs/grupo/job.py" : "/opt/t2c/python_jobs/grupo/job.py"} />
              )}
            </div>

            {type === "spark_submit" && (
              <div className="sm:col-span-2">
                <label className={labelCls}>Classe principal</label>
                <input className={`${inputCls} font-mono text-xs`} value={mainClass} onChange={(e) => setMainClass(e.target.value)} placeholder="com.exemplo.Main" />
              </div>
            )}

            <div>
              <label className={labelCls}>Conexão origem</label>
              <ConnSelect conns={conns} value={sourceConn} onChange={setSourceConn} />
            </div>
            <div>
              <label className={labelCls}>Conexão destino</label>
              <ConnSelect conns={conns} value={targetConn} onChange={setTargetConn} />
            </div>
            <div>
              <label className={labelCls}>Conexão única</label>
              <ConnSelect conns={conns} value={singleConn} onChange={setSingleConn} />
            </div>
            {engine === "spark_cluster" && (
              <div>
                <label className={labelCls}>Cluster ID</label>
                <input className={inputCls} type="number" min={0} value={clusterId} onChange={(e) => setClusterId(e.target.value)} placeholder="—" />
              </div>
            )}

            {/* argumentos builder */}
            <div className="sm:col-span-2">
              <label className={labelCls}>Argumentos (chave/valor)</label>
              <div className="space-y-2">
                {args.map((a, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <input className={`${inputCls} font-mono text-xs`} placeholder="source-connection" value={a.key} onChange={(e) => setArgs((p) => p.map((x, j) => j === i ? { ...x, key: e.target.value } : x))} />
                    <span className="text-gray-400">=</span>
                    <input className={`${inputCls} font-mono text-xs`} placeholder="mysql_1" value={a.value} onChange={(e) => setArgs((p) => p.map((x, j) => j === i ? { ...x, value: e.target.value } : x))} />
                    <button onClick={() => setArgs((p) => p.filter((_, j) => j !== i))} className="rounded-md border border-gray-200 p-2 text-gray-400 hover:bg-red-50 hover:text-red-600"><Trash2 size={14} /></button>
                  </div>
                ))}
                <button onClick={() => setArgs((p) => [...p, { key: "", value: "" }])} className="inline-flex items-center gap-1.5 rounded-md border border-gray-200 bg-white px-2.5 py-1 text-xs font-medium text-gray-600 hover:bg-gray-50">
                  <Plus size={13} /> Adicionar argumento
                </button>
              </div>
              {argString && <pre className="mt-2 overflow-x-auto rounded-lg border border-graphite-800 bg-graphite-950 p-2.5 font-mono text-xs text-slate-200">{argString}</pre>}
            </div>

            <div className="sm:col-span-2">
              <label className={labelCls}>Parâmetros padrão (JSON)</label>
              <textarea className={`${inputCls} font-mono text-xs`} rows={2} value={defaultParams} onChange={(e) => setDefaultParams(e.target.value)} placeholder='{ "chave": "valor" }' />
              {paramsError && <p className="mt-1 text-xs text-red-500">{paramsError}</p>}
            </div>

            <div>
              <label className={labelCls}>Timeout (s)</label>
              <input className={inputCls} type="number" min={0} value={timeout} onChange={(e) => setTimeoutS(e.target.value)} placeholder="Sem limite" />
            </div>
            <div>
              <label className={labelCls}>Retry</label>
              <input className={inputCls} type="number" min={0} value={retry} onChange={(e) => setRetry(e.target.value)} />
            </div>

            <div className="sm:col-span-2">
              <label className={labelCls}>Tags</label>
              <TagInput value={tags} onChange={setTags} allowCreate placeholder="Adicionar tag e Enter…" />
            </div>
            <div className="sm:col-span-2">
              <label className="inline-flex items-center gap-2 text-sm text-gray-700">
                <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} className="h-4 w-4 rounded border-gray-300 text-brand-500 focus:ring-brand-500" />
                Job ativo
              </label>
            </div>
          </div>
        </div>
      )}
    </Modal>
  );
}

function EngineCard({ icon, title, desc, onClick }: { icon: React.ReactNode; title: string; desc: string; onClick: () => void }) {
  return (
    <button onClick={onClick} className="group rounded-2xl border border-gray-200 bg-white p-5 text-left transition-all hover:border-brand-400 hover:shadow-card">
      <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-600 transition-colors group-hover:bg-brand-100">{icon}</div>
      <p className="mt-3 flex items-center gap-1.5 text-base font-bold text-gray-900">{title} <Zap size={14} className="text-brand-400 opacity-0 transition-opacity group-hover:opacity-100" /></p>
      <p className="mt-1 text-sm text-gray-500">{desc}</p>
    </button>
  );
}

function ConnSelect({ conns, value, onChange }: { conns: ConnectionLite[]; value: string; onChange: (v: string) => void }) {
  return (
    <select className={inputCls} value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">—</option>
      {conns.map((c) => (
        <option key={c.id} value={c.id}>
          {c.name} · {c.connection_type}{c.last_test_status === "success" ? " · teste OK" : c.last_test_status === "failed" ? " · teste falhou" : ""}
        </option>
      ))}
    </select>
  );
}
