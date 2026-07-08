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
  useReactFlow,
} from "@xyflow/react";
import type { Connection, Edge, Node } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  CheckCircle2,
  Code2,
  Eye,
  LayoutGrid,
  Play,
  Plus,
  Save,
  Trash2,
  Workflow,
  X,
} from "lucide-react";

import { api, ApiError } from "@/lib/api";
import type { Page } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/cn";
import { PrimaryButton, SecondaryButton, StatusBadge } from "@/components/ui";
import { PipelineJobNode } from "@/features/pipelines/PipelineJobNode";
import { JobSearchCommand } from "@/features/pipelines/JobSearchCommand";
import type { JobSearchResult } from "@/features/pipelines/JobSearchCommand";
import { autoLayout } from "@/features/pipelines/layout";
import type { Graph, JobLite, PipelineDetail, ValidationResult } from "@/features/pipelines/types";
import { fmtDate } from "@/features/pipelines/types";

const nodeTypes = { jobNode: PipelineJobNode };
const EDGE_COLOR: Record<string, string> = { waiting: "#cbd5e1", released: "#f97316", success: "#10b981", blocked: "#ef4444", skipped: "#e2e8f0" };
const TERMINAL = ["success", "failed", "cancelled", "partial_success"];

interface GraphStatus {
  pipeline_execution_id: number;
  status: string;
  nodes: { step_id: number; step_key: string | null; job_id: number; status: string; duration_seconds: number | null }[];
  edges: { source_step_id: number; target_step_id: number; status: string }[];
}

function sanitizeKey(name: string, taken: Set<string>): string {
  const base = "step_" + (name.replace(/[^a-zA-Z0-9_]+/g, "_").replace(/^_+|_+$/g, "").toLowerCase() || "job");
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
  const { screenToFlowPosition, fitView } = useReactFlow();

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [dirty, setDirty] = useState(false);
  const [sel, setSel] = useState<{ kind: "node" | "edge"; id: string } | null>(null);
  const [validation, setValidation] = useState<ValidationResult | null>(null);
  const [bottomTab, setBottomTab] = useState<"validacoes" | "execucao" | "logs">("validacoes");
  const [toast, setToast] = useState<{ kind: "ok" | "err"; msg: string } | null>(null);
  const [execId, setExecId] = useState<number | null>(pipeline.last_execution_id ?? null);
  const [watch, setWatch] = useState(false);
  const [search, setSearch] = useState<{ source: string | null; pos: { x: number; y: number } | null } | null>(null);
  const seeded = useRef(false);
  const connectFrom = useRef<string | null>(null);

  const jobsQ = useQuery({ queryKey: ["jobs-builder"], queryFn: () => api.get<Page<JobLite>>("/api/v1/jobs?page=1&page_size=200") });
  const graphQ = useQuery({ queryKey: ["pipeline-graph", pid], queryFn: () => api.get<Graph>(`/api/v1/pipelines/${pid}/graph`) });
  const jobsById = useMemo(() => new Map((jobsQ.data?.items ?? []).map((j) => [j.id, j])), [jobsQ.data]);

  const statusQ = useQuery({
    queryKey: ["graph-status", execId],
    queryFn: () => api.get<GraphStatus>(`/api/v1/pipeline-executions/${execId}/graph-status`),
    enabled: watch && !!execId,
    refetchInterval: (query) => (TERMINAL.includes((query.state.data as GraphStatus | undefined)?.status ?? "") ? false : 3000),
  });

  useEffect(() => {
    if (seeded.current || !graphQ.data || jobsById.size === 0) return;
    seeded.current = true;
    setNodes(graphQ.data.nodes.map((n) => {
      const job = jobsById.get(n.job_id);
      return { id: n.step_key, type: "jobNode", position: n.position ?? { x: 0, y: 0 },
        data: { label: n.label ?? n.step_key, jobId: n.job_id, jobName: job?.name ?? `#${n.job_id}`, jobType: job?.type ?? "?", engine: job?.engine ?? null, active: n.active, run_if: n.run_if, retry_count: n.retry_count, timeout_seconds: n.timeout_seconds } } as Node;
    }));
    setEdges(graphQ.data.edges.map((e) => ({ id: `${e.source_step_key}->${e.target_step_key}`, source: e.source_step_key, target: e.target_step_key, animated: true, data: { dependency_type: e.dependency_type } })));
  }, [graphQ.data, jobsById, setNodes, setEdges]);

  // Live status → node/edge colors.
  useEffect(() => {
    const gs = statusQ.data;
    if (!gs) return;
    const byKey = new Map<string, { status: string; dur: number | null }>();
    const idToKey = new Map<number, string>();
    gs.nodes.forEach((n) => { if (n.step_key) { byKey.set(n.step_key, { status: n.status, dur: n.duration_seconds }); idToKey.set(n.step_id, n.step_key); } });
    setNodes((nds) => nds.map((n) => { const s = byKey.get(n.id); return s ? { ...n, data: { ...n.data, status: s.status, durationSeconds: s.dur } } : n; }));
    setEdges((eds) => eds.map((e) => {
      const es = gs.edges.find((x) => idToKey.get(x.source_step_id) === e.source && idToKey.get(x.target_step_id) === e.target);
      return es ? { ...e, animated: es.status === "released", style: { stroke: EDGE_COLOR[es.status] ?? "#cbd5e1", strokeWidth: 2 } } : e;
    }));
    if (TERMINAL.includes(gs.status)) { setWatch(false); setToast({ kind: gs.status === "success" ? "ok" : "err", msg: `Pipeline: ${gs.status}` }); }
  }, [statusQ.data, setNodes, setEdges]);

  // ── cycle / duplicate guards ──
  const reaches = useCallback((from: string, to: string, es: Edge[]): boolean => {
    const adj: Record<string, string[]> = {};
    es.forEach((e) => (adj[e.source] ??= []).push(e.target));
    const seen = new Set<string>(); const stack = [from];
    while (stack.length) { const c = stack.pop()!; if (c === to) return true; if (seen.has(c)) continue; seen.add(c); (adj[c] ?? []).forEach((n) => stack.push(n)); }
    return false;
  }, []);

  const tryAddEdge = useCallback((source: string, target: string) => {
    if (source === target) { setToast({ kind: "err", msg: "Um job não pode depender de si mesmo." }); return false; }
    if (edges.some((e) => e.source === source && e.target === target)) { setToast({ kind: "err", msg: "Essa conexão já existe." }); return false; }
    if (reaches(target, source, edges)) { setToast({ kind: "err", msg: "Conexão criaria dependência circular." }); return false; }
    setEdges((eds) => addEdge({ id: `${source}->${target}`, source, target, animated: true, data: { dependency_type: "success" } }, eds));
    setDirty(true);
    return true;
  }, [edges, reaches, setEdges]);

  const onConnect = useCallback((c: Connection) => { if (canWrite && !watch && c.source && c.target) tryAddEdge(c.source, c.target); }, [canWrite, watch, tryAddEdge]);

  const onConnectStart = useCallback((_: unknown, p: { nodeId: string | null }) => { connectFrom.current = p.nodeId; }, []);
  const onConnectEnd = useCallback((event: MouseEvent | TouchEvent) => {
    if (!canWrite || watch) return;
    const target = event.target as Element | null;
    const droppedOnPane = target?.classList?.contains("react-flow__pane");
    if (droppedOnPane && connectFrom.current) {
      const { clientX, clientY } = "changedTouches" in event ? event.changedTouches[0] : (event as MouseEvent);
      const pos = screenToFlowPosition({ x: clientX, y: clientY });
      setSearch({ source: connectFrom.current, pos });
    }
    connectFrom.current = null;
  }, [canWrite, watch, screenToFlowPosition]);

  function addJob(job: JobSearchResult | JobLite, pos?: { x: number; y: number }, connectSource?: string | null) {
    const taken = new Set(nodes.map((n) => n.id));
    const key = sanitizeKey(job.name, taken);
    const jobType = "job_type" in job ? job.job_type : job.type;
    const position = pos ?? { x: 120 + (nodes.length % 3) * 300, y: 100 + Math.floor(nodes.length / 3) * 170 };
    setNodes((nds) => [...nds, { id: key, type: "jobNode", position,
      data: { label: job.name, jobId: job.id, jobName: job.name, jobType, engine: job.engine, active: "active" in job ? job.active : job.is_active, run_if: "success", retry_count: 0, timeout_seconds: null, onQuickAdd: (nid: string) => setSearch({ source: nid, pos: null }) } } as Node]);
    setDirty(true);
    if (connectSource) tryAddEdge(connectSource, key);
    if (!("active" in job ? job.active : job.is_active)) setToast({ kind: "err", msg: `Atenção: "${job.name}" está inativo.` });
  }

  function onSearchSelect(job: JobSearchResult) {
    const src = search?.source ?? null;
    let pos = search?.pos ?? undefined;
    if (!pos && src) { const s = nodes.find((n) => n.id === src); if (s) pos = { x: s.position.x + 300, y: s.position.y }; }
    addJob(job, pos, src);
    setSearch(null);
  }

  function removeSelected() {
    if (!sel || watch) return;
    if (sel.kind === "node") { setNodes((nds) => nds.filter((n) => n.id !== sel.id)); setEdges((eds) => eds.filter((e) => e.source !== sel.id && e.target !== sel.id)); }
    else setEdges((eds) => eds.filter((e) => e.id !== sel.id));
    setSel(null); setDirty(true);
  }

  function organize() { setNodes((nds) => autoLayout(nds, edges)); setDirty(true); setTimeout(() => fitView({ padding: 0.2 }), 60); }

  function toPayload(): Graph {
    return {
      nodes: nodes.map((n) => ({ step_key: n.id, job_id: n.data.jobId as number, label: (n.data.label as string) ?? n.id, position: { x: Math.round(n.position.x), y: Math.round(n.position.y) }, run_if: (n.data.run_if as string) ?? "success", retry_count: (n.data.retry_count as number) ?? 0, timeout_seconds: (n.data.timeout_seconds as number) ?? null, parameters: {}, active: (n.data.active as boolean) ?? true })),
      edges: edges.map((e) => ({ source_step_key: e.source, target_step_key: e.target, dependency_type: (e.data?.dependency_type as string) ?? "success" })),
    };
  }
  async function validate() { const res = await api.post<ValidationResult>(`/api/v1/pipelines/${pid}/validate`, toPayload()); setValidation(res); setBottomTab("validacoes"); }
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

  // Ctrl+K / A to open the command palette (edit mode).
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const typing = ["INPUT", "TEXTAREA", "SELECT"].includes((e.target as HTMLElement)?.tagName);
      if (!canWrite || watch) return;
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setSearch({ source: null, pos: null }); }
      else if (!typing && e.key.toLowerCase() === "a" && !search) { setSearch({ source: null, pos: null }); }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [canWrite, watch, search]);

  function tryClose() { if (dirty && !watch && !window.confirm("Existem alterações não salvas. Deseja sair mesmo assim?")) return; onClose(); }

  const selNode = sel?.kind === "node" ? nodes.find((n) => n.id === sel.id) : null;
  const selEdge = sel?.kind === "edge" ? edges.find((e) => e.id === sel.id) : null;
  const patchNode = (patch: Record<string, unknown>) => { setNodes((nds) => nds.map((n) => (n.id === sel?.id ? { ...n, data: { ...n.data, ...patch } } : n))); setDirty(true); };
  const patchEdge = (patch: Record<string, unknown>) => { setEdges((eds) => eds.map((e) => (e.id === sel?.id ? { ...e, data: { ...e.data, ...patch } } : e))); setDirty(true); };
  const headerTone = watch && statusQ.data?.status === "success" ? "border-emerald-200 bg-emerald-50" : watch && statusQ.data && TERMINAL.includes(statusQ.data.status) ? "border-red-200 bg-red-50" : "border-gray-200 bg-white";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="flex h-[90vh] w-[95vw] flex-col overflow-hidden rounded-2xl bg-white shadow-2xl">
        {/* Toolbar */}
        <div className={cn("flex items-center justify-between border-b px-5 py-3", headerTone)}>
          <div className="flex items-center gap-3">
            <h2 className="text-base font-bold text-gray-900">Pipeline Builder · {pipeline.name}</h2>
            <StatusBadge status={pipeline.is_active ? "active" : "inactive"} />
            <span className="text-xs text-gray-500">{nodes.length} jobs · {edges.length} conexões</span>
            {pipeline.last_finished_at && <span className="text-xs text-gray-400">última exec: {fmtDate(pipeline.last_finished_at)}</span>}
            {dirty && <span className="inline-flex items-center gap-1 rounded-full bg-brand-100 px-2 py-0.5 text-xs font-medium text-brand-700"><span className="h-1.5 w-1.5 rounded-full bg-brand-500" /> não salvo</span>}
            {watch && <span className="inline-flex items-center gap-1 rounded-full bg-brand-100 px-2 py-0.5 text-xs font-medium text-brand-700">acompanhando #{execId}</span>}
          </div>
          <div className="flex items-center gap-2">
            {canWrite && <PrimaryButton size="sm" icon={<Plus size={15} />} onClick={() => setSearch({ source: null, pos: null })} disabled={watch}>Adicionar job</PrimaryButton>}
            <SecondaryButton size="sm" icon={<CheckCircle2 size={15} />} onClick={validate}>Validar</SecondaryButton>
            {canWrite && <SecondaryButton size="sm" icon={<LayoutGrid size={15} />} onClick={organize} disabled={watch}>Organizar</SecondaryButton>}
            {canWrite && <SecondaryButton size="sm" icon={<Save size={15} />} onClick={() => save.mutate()} disabled={watch || save.isPending}>Salvar</SecondaryButton>}
            {canRun && <PrimaryButton size="sm" icon={<Play size={15} />} onClick={() => run.mutate()} loading={run.isPending} disabled={watch}>Executar</PrimaryButton>}
            <button onClick={tryClose} className="ml-1 flex h-8 w-8 items-center justify-center rounded-lg text-gray-500 hover:bg-gray-100"><X size={18} /></button>
          </div>
        </div>

        {watch && <div className="bg-brand-50 px-5 py-1.5 text-xs text-brand-700">Pipeline em execução. A edição está bloqueada até finalizar.</div>}

        <div className="flex min-h-0 flex-1">
          {/* Canvas (occupies almost everything) */}
          <div className="relative min-w-0 flex-1 bg-slate-50">
            {toast && <div className={cn("absolute left-1/2 top-3 z-30 -translate-x-1/2 rounded-lg border px-3 py-1.5 text-sm shadow-card", toast.kind === "ok" ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-red-200 bg-red-50 text-red-700")}>{toast.msg}</div>}

            {nodes.length === 0 && !graphQ.isLoading && (
              <div className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center">
                <div className="pointer-events-auto flex flex-col items-center gap-3 rounded-2xl border border-dashed border-gray-300 bg-white/80 px-10 py-8 text-center">
                  <Workflow size={28} className="text-brand-500" />
                  <div><p className="font-medium text-gray-800">Nenhum job adicionado ao pipeline</p><p className="text-sm text-gray-500">Comece adicionando um job cadastrado.</p></div>
                  {canWrite && <PrimaryButton icon={<Plus size={16} />} onClick={() => setSearch({ source: null, pos: null })}>Adicionar job</PrimaryButton>}
                </div>
              </div>
            )}

            <ReactFlow
              nodes={nodes} edges={edges} nodeTypes={nodeTypes}
              onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onConnect={onConnect}
              onConnectStart={onConnectStart} onConnectEnd={onConnectEnd}
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

            <JobSearchCommand
              open={!!search}
              title={search?.source ? "Próximo job" : "Adicionar job"}
              onSelect={onSearchSelect}
              onClose={() => setSearch(null)}
            />
          </div>

          {/* Right panel (only when something selected) */}
          {(selNode || selEdge) && (
            <div className="w-72 shrink-0 overflow-y-auto border-l border-gray-200 p-4">
              {selNode ? (
                <NodePanel node={selNode} watch={watch} canWrite={canWrite} navigate={navigate} onPatch={patchNode} onRemove={removeSelected} onAddNext={(id) => setSearch({ source: id, pos: null })} />
              ) : selEdge ? (
                <div className="space-y-3 text-sm">
                  <div className="flex items-center justify-between"><h3 className="font-semibold text-gray-900">Conexão</h3>{canWrite && !watch && <button onClick={removeSelected} className="inline-flex items-center gap-1 text-xs text-red-600 hover:underline"><Trash2 size={13} /> Remover</button>}</div>
                  <div className="text-xs text-gray-500">{selEdge.source} → {selEdge.target}</div>
                  <div><span className="text-xs font-medium text-gray-500">Tipo de dependência</span>
                    <select disabled={!canWrite || watch} className="mt-1 w-full rounded-lg border border-gray-200 px-2.5 py-1.5 text-sm" value={(selEdge.data?.dependency_type as string) ?? "success"} onChange={(e) => patchEdge({ dependency_type: e.target.value })}>{["success", "finished", "failed", "always"].map((r) => <option key={r} value={r}>{r}</option>)}</select>
                  </div>
                </div>
              ) : null}
            </div>
          )}
        </div>

        {/* Bottom panel */}
        <div className="h-44 shrink-0 border-t border-gray-200">
          <div className="flex gap-1 border-b border-gray-100 px-4">
            {(["validacoes", "execucao", "logs"] as const).map((t) => (
              <button key={t} onClick={() => setBottomTab(t)} className={cn("border-b-2 px-3 py-2 text-sm font-medium", bottomTab === t ? "border-brand-500 text-brand-600" : "border-transparent text-gray-500 hover:text-gray-700")}>
                {t === "validacoes" ? "Validações" : t === "execucao" ? "Execução" : "Logs"}
              </button>
            ))}
          </div>
          <div className="h-[calc(100%-41px)] overflow-y-auto p-3 text-sm">
            {bottomTab === "validacoes" && <ValidationPanel v={validation} />}
            {bottomTab === "execucao" && <TimelinePanel execId={execId} />}
            {bottomTab === "logs" && <StepLogsPanel execId={execId} nodes={statusQ.data?.nodes} selKey={selNode?.id ?? null} />}
          </div>
        </div>
      </div>
    </div>
  );
}

function NodePanel({ node, watch, canWrite, navigate, onPatch, onRemove, onAddNext }: {
  node: Node; watch: boolean; canWrite: boolean; navigate: (to: string) => void;
  onPatch: (p: Record<string, unknown>) => void; onRemove: () => void; onAddNext: (id: string) => void;
}) {
  const d = node.data as Record<string, unknown>;
  const inp = "mt-1 w-full rounded-lg border border-gray-200 px-2.5 py-1.5 text-sm focus:border-brand-400 focus:outline-none";
  return (
    <div className="space-y-3 text-sm">
      <div className="flex items-center justify-between"><h3 className="font-semibold text-gray-900">Step</h3>{canWrite && !watch && <button onClick={onRemove} className="inline-flex items-center gap-1 text-xs text-red-600 hover:underline"><Trash2 size={13} /> Remover</button>}</div>
      <div className="text-xs text-gray-500">Job: <span className="font-medium text-gray-700">{d.jobName as string}</span> · {d.jobType as string} · {(d.engine as string) ?? "—"}</div>
      {d.status ? <div className="rounded-lg border border-gray-100 bg-gray-50 p-2 text-xs">Status: <b>{d.status as string}</b>{d.durationSeconds != null ? ` · ${d.durationSeconds}s` : ""}</div> : null}

      {/* Quick actions */}
      <div className="flex flex-wrap gap-1.5">
        {canWrite && !watch && <button onClick={() => onAddNext(node.id)} className="inline-flex items-center gap-1 rounded-lg border border-gray-200 px-2 py-1 text-xs hover:bg-brand-50"><Plus size={12} /> Próximo job</button>}
        <button onClick={() => navigate(`/jobs/${d.jobId}`)} className="inline-flex items-center gap-1 rounded-lg border border-gray-200 px-2 py-1 text-xs hover:bg-gray-50"><Eye size={12} /> Detalhes</button>
        <button onClick={() => navigate(`/jobs/${d.jobId}`)} className="inline-flex items-center gap-1 rounded-lg border border-gray-200 px-2 py-1 text-xs hover:bg-gray-50"><Code2 size={12} /> Código</button>
      </div>

      {!watch && canWrite && (
        <>
          <div><span className="text-xs font-medium text-gray-500">Nome do step</span><input className={inp} value={(d.label as string) ?? ""} onChange={(e) => onPatch({ label: e.target.value })} /></div>
          <div><span className="text-xs font-medium text-gray-500">Run if</span><select className={inp} value={(d.run_if as string) ?? "success"} onChange={(e) => onPatch({ run_if: e.target.value })}>{["success", "finished", "failed", "always"].map((r) => <option key={r} value={r}>{r}</option>)}</select></div>
          <div className="grid grid-cols-2 gap-2">
            <div><span className="text-xs font-medium text-gray-500">Retry</span><input type="number" className={inp} value={(d.retry_count as number) ?? 0} onChange={(e) => onPatch({ retry_count: Number(e.target.value) })} /></div>
            <div><span className="text-xs font-medium text-gray-500">Timeout</span><input type="number" className={inp} value={(d.timeout_seconds as number) ?? ""} onChange={(e) => onPatch({ timeout_seconds: e.target.value ? Number(e.target.value) : null })} /></div>
          </div>
          <label className="flex items-center gap-2"><input type="checkbox" className="h-4 w-4 rounded border-gray-300 text-brand-500" checked={(d.active as boolean) ?? true} onChange={(e) => onPatch({ active: e.target.checked })} /> Ativo</label>
        </>
      )}
    </div>
  );
}

function ValidationPanel({ v }: { v: ValidationResult | null }) {
  if (!v) return <p className="text-gray-400">Clique em <b>Validar</b> para checar o pipeline.</p>;
  return (
    <div className="space-y-1">
      <p className={cn("flex items-center gap-1.5 font-medium", v.valid ? "text-emerald-600" : "text-red-600")}>{v.valid ? <CheckCircle2 size={15} /> : <AlertTriangle size={15} />}{v.valid ? "Pipeline válido" : "Pipeline inválido"}</p>
      {v.errors.map((e, i) => <p key={i} className="rounded bg-red-50 px-2 py-1 text-xs text-red-700">{e}</p>)}
      {v.warnings.map((w, i) => <p key={i} className="rounded bg-amber-50 px-2 py-1 text-xs text-amber-700">{w}</p>)}
    </div>
  );
}

function TimelinePanel({ execId }: { execId: number | null }) {
  const { data } = useQuery({ queryKey: ["pipeline-timeline", execId], queryFn: () => api.get<{ time: string; step_id: number; event: string; status: string }[]>(`/api/v1/pipeline-executions/${execId}/timeline`), enabled: !!execId, refetchInterval: 3000 });
  if (!execId) return <p className="text-gray-400">Execute o pipeline para ver a linha do tempo.</p>;
  if (!data?.length) return <p className="text-gray-400">Sem eventos ainda.</p>;
  return <div className="space-y-1 font-mono text-xs">{data.map((e, i) => <div key={i} className="flex gap-3"><span className="text-gray-400">{new Date(e.time).toLocaleTimeString("pt-BR")}</span><span className={cn(e.status === "success" ? "text-emerald-600" : e.status === "failed" ? "text-red-600" : e.status === "skipped" ? "text-gray-400" : "text-brand-600")}>step #{e.step_id} · {e.event}</span></div>)}</div>;
}

function StepLogsPanel({ execId, nodes, selKey }: { execId: number | null; nodes?: GraphStatus["nodes"]; selKey: string | null }) {
  const resolved = selKey && nodes ? nodes.find((n) => n.step_key === selKey)?.step_id ?? null : null;
  const { data } = useQuery({ queryKey: ["pipeline-step-logs", execId, resolved], queryFn: () => api.get<{ lines: { level: string; message: string }[] }>(`/api/v1/pipeline-executions/${execId}/step/${resolved}/logs`), enabled: !!execId && !!resolved });
  if (!execId) return <p className="text-gray-400">Execute o pipeline e selecione um nó para ver os logs do step.</p>;
  if (!selKey) return <p className="text-gray-400">Selecione um nó no canvas.</p>;
  if (!data?.lines?.length) return <p className="text-gray-400">Sem logs para este step ainda.</p>;
  return <div className="scrollbar-dark max-h-full overflow-auto rounded-lg bg-graphite-950 p-2 font-mono text-xs text-slate-200">{data.lines.map((l, i) => <div key={i} className={cn("whitespace-pre-wrap", l.level === "ERROR" && "text-red-400")}>{l.message}</div>)}</div>;
}

export function PipelineBuilderModal({ pipeline, onClose }: { pipeline: PipelineDetail; onClose: () => void }) {
  return (<ReactFlowProvider><InnerBuilder pipeline={pipeline} onClose={onClose} /></ReactFlowProvider>);
}
