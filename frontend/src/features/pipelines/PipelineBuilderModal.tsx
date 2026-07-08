import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  addEdge,
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
} from "@xyflow/react";
import type { Connection, Edge, Node, ReactFlowInstance } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  CheckCircle2,
  LayoutGrid,
  Play,
  Plus,
  Save,
  Search,
  Trash2,
  X,
} from "lucide-react";

import { api, ApiError } from "@/lib/api";
import type { Page } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/cn";
import { PrimaryButton, SecondaryButton, StatusBadge } from "@/components/ui";
import { PipelineJobNode } from "@/features/pipelines/PipelineJobNode";
import { autoLayout } from "@/features/pipelines/layout";
import type {
  Graph,
  JobLite,
  PipelineDetail,
  ValidationResult,
} from "@/features/pipelines/types";
import { fmtDate } from "@/features/pipelines/types";

const nodeTypes = { jobNode: PipelineJobNode };
const EDGE_COLOR: Record<string, string> = {
  waiting: "#cbd5e1", released: "#f97316", success: "#10b981", blocked: "#ef4444", skipped: "#e2e8f0",
};
const TERMINAL = ["success", "failed", "cancelled", "partial_success"];

interface GraphStatus {
  pipeline_execution_id: number;
  status: string;
  nodes: { step_id: number; step_key: string | null; job_id: number; status: string; duration_seconds: number | null; message: string | null; started_at: string | null; finished_at: string | null }[];
  edges: { source_step_id: number; target_step_id: number; status: string }[];
}

function sanitizeKey(name: string, taken: Set<string>): string {
  const base = name.replace(/[^a-zA-Z0-9_]+/g, "_").replace(/^_+|_+$/g, "").toLowerCase() || "job";
  let key = base, i = 2;
  while (taken.has(key)) key = `${base}_${i++}`;
  return key;
}

function InnerBuilder({ pipeline, onClose }: { pipeline: PipelineDetail; onClose: () => void }) {
  const pid = pipeline.id;
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { can } = useAuth();
  const canWrite = can("ingest:pipelines:builder");
  const canRun = can("ingest:pipelines:run");

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [rf, setRf] = useState<ReactFlowInstance | null>(null);
  const [dirty, setDirty] = useState(false);
  const [sel, setSel] = useState<{ kind: "node" | "edge"; id: string } | null>(null);
  const [validation, setValidation] = useState<ValidationResult | null>(null);
  const [bottomTab, setBottomTab] = useState<"validacoes" | "execucao" | "logs">("validacoes");
  const [toast, setToast] = useState<{ kind: "ok" | "err"; msg: string } | null>(null);
  const [q, setQ] = useState("");
  const [execId, setExecId] = useState<number | null>(pipeline.last_execution_id ?? null);
  const [watch, setWatch] = useState(false);
  const [quickAddFor, setQuickAddFor] = useState<string | null>(null);
  const seeded = useRef(false);

  const jobsQ = useQuery({ queryKey: ["jobs-builder"], queryFn: () => api.get<Page<JobLite>>("/api/v1/jobs?page=1&page_size=200") });
  const graphQ = useQuery({ queryKey: ["pipeline-graph", pid], queryFn: () => api.get<Graph>(`/api/v1/pipelines/${pid}/graph`) });
  const jobsById = useMemo(() => new Map((jobsQ.data?.items ?? []).map((j) => [j.id, j])), [jobsQ.data]);

  // Live status polling in watch mode.
  const statusQ = useQuery({
    queryKey: ["graph-status", execId],
    queryFn: () => api.get<GraphStatus>(`/api/v1/pipeline-executions/${execId}/graph-status`),
    enabled: watch && !!execId,
    refetchInterval: (query) => (TERMINAL.includes((query.state.data as GraphStatus | undefined)?.status ?? "") ? false : 3000),
  });

  useEffect(() => {
    if (seeded.current || !graphQ.data || jobsById.size === 0) return;
    seeded.current = true;
    setNodes(graphQ.data.nodes.map((n) => nodeFrom(n.step_key, n.job_id, jobsById.get(n.job_id), n.label, n.position, n.run_if, n.retry_count, n.timeout_seconds, n.active)));
    setEdges(graphQ.data.edges.map((e) => edgeFrom(e.source_step_key, e.target_step_key, e.dependency_type)));
  }, [graphQ.data, jobsById, setNodes, setEdges]);

  // Apply live status onto nodes/edges.
  useEffect(() => {
    const gs = statusQ.data;
    if (!gs) return;
    const statusByKey = new Map<string, { status: string; dur: number | null }>();
    const idToKey = new Map<number, string>();
    gs.nodes.forEach((n) => { if (n.step_key) { statusByKey.set(n.step_key, { status: n.status, dur: n.duration_seconds }); idToKey.set(n.step_id, n.step_key); } });
    setNodes((nds) => nds.map((n) => {
      const s = statusByKey.get(n.id);
      return s ? { ...n, data: { ...n.data, status: s.status, durationSeconds: s.dur } } : n;
    }));
    setEdges((eds) => eds.map((e) => {
      const es = gs.edges.find((x) => idToKey.get(x.source_step_id) === e.source && idToKey.get(x.target_step_id) === e.target);
      const color = es ? EDGE_COLOR[es.status] ?? "#cbd5e1" : undefined;
      return color ? { ...e, animated: es!.status === "released", style: { stroke: color, strokeWidth: 2 } } : e;
    }));
    if (TERMINAL.includes(gs.status)) {
      setWatch(false);
      setToast({ kind: gs.status === "success" ? "ok" : "err", msg: `Pipeline: ${gs.status}` });
    }
  }, [statusQ.data, setNodes, setEdges]);

  const onConnect = useCallback((c: Connection) => {
    if (!canWrite || watch) return;
    setEdges((eds) => addEdge({ ...c, id: `${c.source}->${c.target}`, animated: true, data: { dependency_type: "success" } }, eds));
    setDirty(true);
  }, [canWrite, watch, setEdges]);

  function addJob(job: JobLite, near?: { x: number; y: number }) {
    const taken = new Set(nodes.map((n) => n.id));
    const key = sanitizeKey(job.name, taken);
    const pos = near ?? { x: 80 + (nodes.length % 3) * 300, y: 80 + Math.floor(nodes.length / 3) * 170 };
    setNodes((nds) => [...nds, nodeFromJob(key, job, pos, quickAddCb)]);
    setDirty(true);
    if (!job.is_active) setToast({ kind: "err", msg: `Atenção: o job "${job.name}" está inativo.` });
    return key;
  }

  const quickAddCb = useCallback((nodeId: string) => setQuickAddFor(nodeId), []);

  function quickAddJob(job: JobLite) {
    const src = nodes.find((n) => n.id === quickAddFor);
    const pos = src ? { x: src.position.x + 300, y: src.position.y } : undefined;
    const key = addJob(job, pos);
    if (quickAddFor) {
      setEdges((eds) => addEdge({ id: `${quickAddFor}->${key}`, source: quickAddFor, target: key, animated: true, data: { dependency_type: "success" } }, eds));
    }
    setQuickAddFor(null);
  }

  function removeSelected() {
    if (!sel || watch) return;
    if (sel.kind === "node") {
      setNodes((nds) => nds.filter((n) => n.id !== sel.id));
      setEdges((eds) => eds.filter((e) => e.source !== sel.id && e.target !== sel.id));
    } else {
      setEdges((eds) => eds.filter((e) => e.id !== sel.id));
    }
    setSel(null);
    setDirty(true);
  }

  function organize() {
    setNodes((nds) => autoLayout(nds, edges));
    setDirty(true);
    setTimeout(() => rf?.fitView({ padding: 0.2 }), 50);
  }

  function toPayload(): Graph {
    return {
      nodes: nodes.map((n) => ({
        step_key: n.id, job_id: n.data.jobId as number, label: (n.data.label as string) ?? n.id,
        position: { x: Math.round(n.position.x), y: Math.round(n.position.y) },
        run_if: (n.data.run_if as string) ?? "success", retry_count: (n.data.retry_count as number) ?? 0,
        timeout_seconds: (n.data.timeout_seconds as number) ?? null, parameters: {}, active: (n.data.active as boolean) ?? true,
      })),
      edges: edges.map((e) => ({ source_step_key: e.source, target_step_key: e.target, dependency_type: (e.data?.dependency_type as string) ?? "success" })),
    };
  }

  async function validate() {
    const res = await api.post<ValidationResult>(`/api/v1/pipelines/${pid}/validate`, toPayload());
    setValidation(res); setBottomTab("validacoes");
  }
  const save = useMutation({
    mutationFn: () => api.put(`/api/v1/pipelines/${pid}/graph`, toPayload()),
    onSuccess: () => { setDirty(false); setValidation({ valid: true, errors: [], warnings: [] }); setToast({ kind: "ok", msg: "Pipeline salvo." }); qc.invalidateQueries({ queryKey: ["pipeline", pid] }); },
    onError: (err) => { if (err instanceof ApiError && err.status === 422) { setToast({ kind: "err", msg: "Graph inválido — veja Validações." }); void validate(); } else setToast({ kind: "err", msg: err instanceof Error ? err.message : "Falha ao salvar." }); },
  });
  const run = useMutation({
    mutationFn: () => api.post<{ id: number }>(`/api/v1/pipelines/${pid}/run`, {}),
    onSuccess: (pe) => { setExecId(pe.id); setWatch(true); setBottomTab("execucao"); setToast({ kind: "ok", msg: "Execução iniciada — acompanhando." }); },
    onError: (err) => { setToast({ kind: "err", msg: err instanceof Error ? err.message : "Falha ao executar." }); void validate(); },
  });

  useEffect(() => { if (!toast) return; const t = setTimeout(() => setToast(null), 3500); return () => clearTimeout(t); }, [toast]);

  function tryClose() {
    if (dirty && !watch && !window.confirm("Existem alterações não salvas. Deseja sair mesmo assim?")) return;
    onClose();
  }

  const selNode = sel?.kind === "node" ? nodes.find((n) => n.id === sel.id) : null;
  const selEdge = sel?.kind === "edge" ? edges.find((e) => e.id === sel.id) : null;
  const filteredJobs = (jobsQ.data?.items ?? []).filter((j) => !q || j.name.toLowerCase().includes(q.toLowerCase()));
  const patchNode = (patch: Record<string, unknown>) => { setNodes((nds) => nds.map((n) => (n.id === sel?.id ? { ...n, data: { ...n.data, ...patch } } : n))); setDirty(true); };
  const patchEdge = (patch: Record<string, unknown>) => { setEdges((eds) => eds.map((e) => (e.id === sel?.id ? { ...e, data: { ...e.data, ...patch } } : e))); setDirty(true); };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onKeyDown={(e) => e.key === "Escape" && tryClose()}>
      <div className="flex h-[90vh] w-[95vw] flex-col overflow-hidden rounded-2xl bg-white shadow-2xl">
        {/* Header */}
        <div className={cn("flex items-center justify-between border-b px-5 py-3",
          watch && statusQ.data?.status === "success" ? "border-emerald-200 bg-emerald-50" :
          watch && statusQ.data && TERMINAL.includes(statusQ.data.status) && statusQ.data.status !== "success" ? "border-red-200 bg-red-50" : "border-gray-200 bg-white")}>
          <div className="flex items-center gap-3">
            <h2 className="text-base font-bold text-gray-900">Pipeline Builder · {pipeline.name}</h2>
            <StatusBadge status={pipeline.is_active ? "active" : "inactive"} />
            <span className="text-xs text-gray-500">{nodes.length} jobs · {edges.length} conexões</span>
            {pipeline.last_finished_at && <span className="text-xs text-gray-400">última exec: {fmtDate(pipeline.last_finished_at)}</span>}
            {dirty && <span className="inline-flex items-center gap-1 rounded-full bg-brand-100 px-2 py-0.5 text-xs font-medium text-brand-700"><span className="h-1.5 w-1.5 rounded-full bg-brand-500" /> não salvo</span>}
            {watch && <span className="inline-flex items-center gap-1 rounded-full bg-brand-100 px-2 py-0.5 text-xs font-medium text-brand-700">acompanhando execução #{execId}</span>}
          </div>
          <div className="flex items-center gap-2">
            <SecondaryButton size="sm" icon={<CheckCircle2 size={15} />} onClick={validate}>Validar</SecondaryButton>
            {canWrite && <SecondaryButton size="sm" icon={<LayoutGrid size={15} />} onClick={organize} disabled={watch}>Organizar</SecondaryButton>}
            {canWrite && <PrimaryButton size="sm" icon={<Save size={15} />} onClick={() => save.mutate()} disabled={watch || save.isPending}>Salvar</PrimaryButton>}
            {canRun && <PrimaryButton size="sm" icon={<Play size={15} />} onClick={() => run.mutate()} loading={run.isPending} disabled={watch}>Executar</PrimaryButton>}
            <button onClick={tryClose} className="ml-1 flex h-8 w-8 items-center justify-center rounded-lg text-gray-500 hover:bg-gray-100"><X size={18} /></button>
          </div>
        </div>

        {watch && (
          <div className="bg-brand-50 px-5 py-1.5 text-xs text-brand-700">Pipeline em execução. A edição do grafo está bloqueada até finalizar.</div>
        )}

        <div className="flex min-h-0 flex-1">
          {/* Jobs sidebar */}
          <div className={cn("flex w-60 shrink-0 flex-col border-r border-gray-200 bg-gray-50/50 p-3", watch && "pointer-events-none opacity-50")}>
            <div className="relative mb-2">
              <Search size={15} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" />
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar job…" className="h-9 w-full rounded-lg border border-gray-200 pl-8 pr-2 text-sm focus:border-brand-400 focus:outline-none" />
            </div>
            <div className="flex-1 space-y-1 overflow-y-auto">
              {filteredJobs.map((j) => (
                <button key={j.id} onClick={() => canWrite && addJob(j)} disabled={!canWrite}
                  className="flex w-full items-center justify-between rounded-lg border border-gray-100 bg-white px-2.5 py-2 text-left text-sm hover:border-brand-200 hover:bg-brand-50/40 disabled:opacity-50">
                  <div className="min-w-0"><div className="truncate font-medium text-gray-800">{j.name}</div><div className="text-[11px] text-gray-400">{j.type}{!j.is_active && " · inativo"}</div></div>
                  <Plus size={15} className="shrink-0 text-brand-500" />
                </button>
              ))}
            </div>
          </div>

          {/* Canvas */}
          <div className="relative min-w-0 flex-1 bg-slate-50">
            {toast && <div className={cn("absolute left-1/2 top-3 z-20 -translate-x-1/2 rounded-lg border px-3 py-1.5 text-sm shadow-card", toast.kind === "ok" ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-red-200 bg-red-50 text-red-700")}>{toast.msg}</div>}
            <ReactFlow
              nodes={nodes} edges={edges} nodeTypes={nodeTypes} onInit={setRf}
              onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onConnect={onConnect}
              onNodeDragStop={() => setDirty(true)}
              onNodeClick={(_, n) => setSel({ kind: "node", id: n.id })}
              onEdgeClick={(_, e) => setSel({ kind: "edge", id: e.id })}
              onPaneClick={() => setSel(null)}
              nodesDraggable={!watch} nodesConnectable={canWrite && !watch} edgesFocusable={!watch}
              fitView proOptions={{ hideAttribution: true }}
            >
              <Background color="#cbd5e1" gap={18} />
              <Controls showInteractive={false} />
              <MiniMap pannable zoomable className="!bg-white" />
            </ReactFlow>

            {/* Quick-add job picker */}
            {quickAddFor && (
              <div className="absolute right-4 top-4 z-30 w-64 rounded-xl border border-gray-200 bg-white p-3 shadow-card-hover">
                <div className="mb-2 flex items-center justify-between text-sm font-semibold text-gray-800">Próximo job de "{quickAddFor}"<button onClick={() => setQuickAddFor(null)}><X size={15} className="text-gray-400" /></button></div>
                <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar…" className="mb-2 h-8 w-full rounded-lg border border-gray-200 px-2 text-sm focus:border-brand-400 focus:outline-none" />
                <div className="max-h-52 space-y-1 overflow-y-auto">
                  {filteredJobs.map((j) => <button key={j.id} onClick={() => quickAddJob(j)} className="block w-full truncate rounded-lg px-2 py-1.5 text-left text-sm hover:bg-brand-50">{j.name}</button>)}
                </div>
              </div>
            )}
          </div>

          {/* Right panel */}
          <div className="w-72 shrink-0 overflow-y-auto border-l border-gray-200 p-4">
            {selNode ? (
              <NodePanel node={selNode} watch={watch} canWrite={canWrite} navigate={navigate}
                onPatch={patchNode} onRemove={removeSelected} />
            ) : selEdge ? (
              <div className="space-y-3 text-sm">
                <div className="flex items-center justify-between"><h3 className="font-semibold text-gray-900">Conexão</h3>{canWrite && !watch && <button onClick={removeSelected} className="inline-flex items-center gap-1 text-xs text-red-600 hover:underline"><Trash2 size={13} /> Remover</button>}</div>
                <div className="text-xs text-gray-500">{selEdge.source} → {selEdge.target}</div>
                <div>
                  <span className="text-xs font-medium text-gray-500">Tipo de dependência</span>
                  <select disabled={!canWrite || watch} className="mt-1 w-full rounded-lg border border-gray-200 px-2.5 py-1.5 text-sm" value={(selEdge.data?.dependency_type as string) ?? "success"} onChange={(e) => patchEdge({ dependency_type: e.target.value })}>
                    {["success", "finished", "failed", "always"].map((r) => <option key={r} value={r}>{r}</option>)}
                  </select>
                </div>
              </div>
            ) : (
              <div className="text-xs text-gray-400">
                {watch ? "Clique num nó para ver status e logs do step." : "Arraste jobs para o canvas, conecte pela bolinha laranja (ou use o + no nó). Clique num nó/conexão para editar."}
              </div>
            )}
          </div>
        </div>

        {/* Bottom panel */}
        <div className="h-44 shrink-0 border-t border-gray-200">
          <div className="flex gap-1 border-b border-gray-100 px-4">
            {(["validacoes", "execucao", "logs"] as const).map((t) => (
              <button key={t} onClick={() => setBottomTab(t)} className={cn("border-b-2 px-3 py-2 text-sm font-medium capitalize", bottomTab === t ? "border-brand-500 text-brand-600" : "border-transparent text-gray-500 hover:text-gray-700")}>
                {t === "validacoes" ? "Validações" : t === "execucao" ? "Execução" : "Logs"}
              </button>
            ))}
          </div>
          <div className="h-[calc(100%-41px)] overflow-y-auto p-3 text-sm">
            {bottomTab === "validacoes" && <ValidationPanel v={validation} />}
            {bottomTab === "execucao" && <TimelinePanel execId={watch || execId ? execId : null} />}
            {bottomTab === "logs" && <StepLogsPanel execId={execId} stepExecId={selNode ? (statusQ.data?.nodes.find((n) => n.step_key === selNode.id)?.step_id ?? null) : null} nodes={statusQ.data?.nodes} selKey={selNode?.id ?? null} />}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── helpers to build RF nodes/edges ──
function nodeFromJob(key: string, job: JobLite, pos: { x: number; y: number }, onQuickAdd: (id: string) => void): Node {
  return { id: key, type: "jobNode", position: pos, data: { label: job.name, jobId: job.id, jobName: job.name, jobType: job.type, engine: job.engine, active: job.is_active, run_if: "success", retry_count: 0, timeout_seconds: null, onQuickAdd } } as Node;
}
function nodeFrom(key: string, jobId: number, job: JobLite | undefined, label: string | null, position: { x: number; y: number } | null, runIf: string, retry: number, timeout: number | null, active: boolean): Node {
  return { id: key, type: "jobNode", position: position ?? { x: 0, y: 0 }, data: { label: label ?? key, jobId, jobName: job?.name ?? `#${jobId}`, jobType: job?.type ?? "?", engine: job?.engine ?? null, active, run_if: runIf, retry_count: retry, timeout_seconds: timeout } } as Node;
}
function edgeFrom(src: string, tgt: string, dep: string): Edge {
  return { id: `${src}->${tgt}`, source: src, target: tgt, animated: true, data: { dependency_type: dep } };
}

function NodePanel({ node, watch, canWrite, navigate, onPatch, onRemove }: {
  node: Node; watch: boolean; canWrite: boolean;
  navigate: (to: string) => void; onPatch: (p: Record<string, unknown>) => void; onRemove: () => void;
}) {
  const d = node.data as Record<string, unknown>;
  const inp = "mt-1 w-full rounded-lg border border-gray-200 px-2.5 py-1.5 text-sm focus:border-brand-400 focus:outline-none";
  return (
    <div className="space-y-3 text-sm">
      <div className="flex items-center justify-between"><h3 className="font-semibold text-gray-900">Step</h3>{canWrite && !watch && <button onClick={onRemove} className="inline-flex items-center gap-1 text-xs text-red-600 hover:underline"><Trash2 size={13} /> Remover</button>}</div>
      <div className="text-xs text-gray-500">Job: <span className="font-medium text-gray-700">{d.jobName as string}</span> · {d.jobType as string} · {(d.engine as string) ?? "—"}</div>
      {d.status ? (
        <div className="rounded-lg border border-gray-100 bg-gray-50 p-2 text-xs">
          <div>Status: <b>{d.status as string}</b>{d.durationSeconds != null ? ` · ${d.durationSeconds}s` : ""}</div>
        </div>
      ) : null}
      {!watch && canWrite && (
        <>
          <div><span className="text-xs font-medium text-gray-500">Nome do step</span><input className={inp} value={(d.label as string) ?? ""} onChange={(e) => onPatch({ label: e.target.value })} /></div>
          <div><span className="text-xs font-medium text-gray-500">Run if</span>
            <select className={inp} value={(d.run_if as string) ?? "success"} onChange={(e) => onPatch({ run_if: e.target.value })}>{["success", "finished", "failed", "always"].map((r) => <option key={r} value={r}>{r}</option>)}</select>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div><span className="text-xs font-medium text-gray-500">Retry</span><input type="number" className={inp} value={(d.retry_count as number) ?? 0} onChange={(e) => onPatch({ retry_count: Number(e.target.value) })} /></div>
            <div><span className="text-xs font-medium text-gray-500">Timeout</span><input type="number" className={inp} value={(d.timeout_seconds as number) ?? ""} onChange={(e) => onPatch({ timeout_seconds: e.target.value ? Number(e.target.value) : null })} /></div>
          </div>
          <label className="flex items-center gap-2"><input type="checkbox" className="h-4 w-4 rounded border-gray-300 text-brand-500" checked={(d.active as boolean) ?? true} onChange={(e) => onPatch({ active: e.target.checked })} /> Ativo</label>
        </>
      )}
      <button onClick={() => navigate(`/jobs/${d.jobId}`)} className="text-xs text-brand-600 hover:underline">Ver detalhes do job →</button>
    </div>
  );
}

function ValidationPanel({ v }: { v: ValidationResult | null }) {
  if (!v) return <p className="text-gray-400">Clique em <b>Validar</b> para checar o pipeline.</p>;
  return (
    <div className="space-y-1">
      <p className={cn("flex items-center gap-1.5 font-medium", v.valid ? "text-emerald-600" : "text-red-600")}>
        {v.valid ? <CheckCircle2 size={15} /> : <AlertTriangle size={15} />}{v.valid ? "Pipeline válido" : "Pipeline inválido"}
      </p>
      {v.errors.map((e, i) => <p key={i} className="rounded bg-red-50 px-2 py-1 text-xs text-red-700">{e}</p>)}
      {v.warnings.map((w, i) => <p key={i} className="rounded bg-amber-50 px-2 py-1 text-xs text-amber-700">{w}</p>)}
    </div>
  );
}

function TimelinePanel({ execId }: { execId: number | null }) {
  const { data } = useQuery({
    queryKey: ["pipeline-timeline", execId],
    queryFn: () => api.get<{ time: string; step_id: number; job_id: number; event: string; status: string }[]>(`/api/v1/pipeline-executions/${execId}/timeline`),
    enabled: !!execId, refetchInterval: 3000,
  });
  if (!execId) return <p className="text-gray-400">Execute o pipeline para ver a linha do tempo.</p>;
  if (!data?.length) return <p className="text-gray-400">Sem eventos ainda.</p>;
  return (
    <div className="space-y-1 font-mono text-xs">
      {data.map((e, i) => (
        <div key={i} className="flex gap-3">
          <span className="text-gray-400">{new Date(e.time).toLocaleTimeString("pt-BR")}</span>
          <span className={cn(e.status === "success" ? "text-emerald-600" : e.status === "failed" ? "text-red-600" : e.status === "skipped" ? "text-gray-400" : "text-brand-600")}>step #{e.step_id} · {e.event}</span>
        </div>
      ))}
    </div>
  );
}

function StepLogsPanel({ execId, stepExecId, nodes, selKey }: { execId: number | null; stepExecId: number | null; nodes?: GraphStatus["nodes"]; selKey: string | null }) {
  // Resolve the step_execution id from the live status by matching the selected node's key.
  const resolved = selKey && nodes ? nodes.find((n) => n.step_key === selKey)?.step_id ?? null : stepExecId;
  const { data } = useQuery({
    queryKey: ["pipeline-step-logs", execId, resolved],
    queryFn: () => api.get<{ lines: { level: string; message: string }[]; status: string }>(`/api/v1/pipeline-executions/${execId}/step/${resolved}/logs`),
    enabled: !!execId && !!resolved,
  });
  if (!execId) return <p className="text-gray-400">Execute o pipeline e selecione um nó para ver os logs do step.</p>;
  if (!selKey) return <p className="text-gray-400">Selecione um nó no canvas.</p>;
  if (!data?.lines?.length) return <p className="text-gray-400">Sem logs para este step ainda.</p>;
  return (
    <div className="scrollbar-dark max-h-full overflow-auto rounded-lg bg-graphite-950 p-2 font-mono text-xs text-slate-200">
      {data.lines.map((l, i) => <div key={i} className={cn("whitespace-pre-wrap", l.level === "ERROR" && "text-red-400")}>{l.message}</div>)}
    </div>
  );
}

export function PipelineBuilderModal({ pipeline, onClose }: { pipeline: PipelineDetail; onClose: () => void }) {
  return (
    <ReactFlowProvider>
      <InnerBuilder pipeline={pipeline} onClose={onClose} />
    </ReactFlowProvider>
  );
}
