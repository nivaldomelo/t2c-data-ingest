import { useCallback, useEffect, useMemo, useState } from "react";
import {
  addEdge,
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  useEdgesState,
  useNodesState,
} from "@xyflow/react";
import type { Connection, Edge, Node } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Plus, Save, Search, Trash2 } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import type { Page } from "@/lib/api";
import { cn } from "@/lib/cn";
import { PrimaryButton, SecondaryButton } from "@/components/ui";
import { PipelineJobNode } from "@/features/pipelines/PipelineJobNode";
import type { Graph, JobLite, ValidationResult } from "@/features/pipelines/types";

const nodeTypes = { jobNode: PipelineJobNode };

function sanitizeKey(name: string, taken: Set<string>): string {
  let base = name.replace(/[^a-zA-Z0-9_]+/g, "_").replace(/^_+|_+$/g, "").toLowerCase() || "job";
  let key = base;
  let i = 2;
  while (taken.has(key)) key = `${base}_${i++}`;
  return key;
}

export function PipelineBuilder({ pipelineId, canWrite }: { pipelineId: number; canWrite: boolean }) {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [selNode, setSelNode] = useState<string | null>(null);
  const [selEdge, setSelEdge] = useState<string | null>(null);
  const [validation, setValidation] = useState<ValidationResult | null>(null);
  const [toast, setToast] = useState<{ kind: "ok" | "err"; msg: string } | null>(null);
  const [q, setQ] = useState("");

  const jobsQ = useQuery({ queryKey: ["jobs-builder"], queryFn: () => api.get<Page<JobLite>>("/api/v1/jobs?page=1&page_size=200") });
  const graphQ = useQuery({ queryKey: ["pipeline-graph", pipelineId], queryFn: () => api.get<Graph>(`/api/v1/pipelines/${pipelineId}/graph`) });
  const jobsById = useMemo(() => new Map((jobsQ.data?.items ?? []).map((j) => [j.id, j])), [jobsQ.data]);

  // Seed canvas from the persisted graph once jobs are known.
  useEffect(() => {
    if (!graphQ.data || jobsById.size === 0) return;
    setNodes(
      graphQ.data.nodes.map((n) => {
        const job = jobsById.get(n.job_id);
        return {
          id: n.step_key,
          type: "jobNode",
          position: n.position ?? { x: 0, y: 0 },
          data: {
            label: n.label ?? n.step_key,
            jobId: n.job_id,
            jobName: job?.name ?? `#${n.job_id}`,
            jobType: job?.type ?? "?",
            engine: job?.engine ?? null,
            active: n.active,
            run_if: n.run_if,
            retry_count: n.retry_count,
            timeout_seconds: n.timeout_seconds,
          },
        } as Node;
      })
    );
    setEdges(
      graphQ.data.edges.map((e) => ({
        id: `${e.source_step_key}->${e.target_step_key}`,
        source: e.source_step_key,
        target: e.target_step_key,
        animated: true,
        data: { dependency_type: e.dependency_type },
      }))
    );
  }, [graphQ.data, jobsById, setNodes, setEdges]);

  const onConnect = useCallback(
    (c: Connection) => setEdges((eds) => addEdge({ ...c, id: `${c.source}->${c.target}`, animated: true, data: { dependency_type: "success" } }, eds)),
    [setEdges]
  );

  function addJob(job: JobLite) {
    const taken = new Set(nodes.map((n) => n.id));
    const key = sanitizeKey(job.name, taken);
    setNodes((nds) => [
      ...nds,
      {
        id: key,
        type: "jobNode",
        position: { x: 80 + (nds.length % 3) * 300, y: 80 + Math.floor(nds.length / 3) * 160 },
        data: { label: job.name, jobId: job.id, jobName: job.name, jobType: job.type, engine: job.engine, active: job.is_active, run_if: "success", retry_count: 0, timeout_seconds: null },
      } as Node,
    ]);
    if (!job.is_active) setToast({ kind: "err", msg: `Atenção: o job "${job.name}" está inativo.` });
  }

  function removeSelected() {
    if (selNode) {
      setNodes((nds) => nds.filter((n) => n.id !== selNode));
      setEdges((eds) => eds.filter((e) => e.source !== selNode && e.target !== selNode));
      setSelNode(null);
    }
    if (selEdge) {
      setEdges((eds) => eds.filter((e) => e.id !== selEdge));
      setSelEdge(null);
    }
  }

  function toPayload(): Graph {
    return {
      nodes: nodes.map((n) => ({
        step_key: n.id,
        job_id: n.data.jobId as number,
        label: (n.data.label as string) ?? n.id,
        position: { x: Math.round(n.position.x), y: Math.round(n.position.y) },
        run_if: (n.data.run_if as string) ?? "success",
        retry_count: (n.data.retry_count as number) ?? 0,
        timeout_seconds: (n.data.timeout_seconds as number) ?? null,
        parameters: {},
        active: (n.data.active as boolean) ?? true,
      })),
      edges: edges.map((e) => ({
        source_step_key: e.source,
        target_step_key: e.target,
        dependency_type: (e.data?.dependency_type as string) ?? "success",
      })),
    };
  }

  async function validate() {
    const res = await api.post<ValidationResult>(`/api/v1/pipelines/${pipelineId}/validate`, toPayload());
    setValidation(res);
    setToast(res.valid ? { kind: "ok", msg: "Pipeline válido." } : { kind: "err", msg: "Pipeline inválido — veja os erros." });
  }

  async function save() {
    try {
      await api.put(`/api/v1/pipelines/${pipelineId}/graph`, toPayload());
      setValidation({ valid: true, errors: [], warnings: [] });
      setToast({ kind: "ok", msg: "Pipeline salvo." });
    } catch (err) {
      if (err instanceof ApiError && err.status === 422) {
        setToast({ kind: "err", msg: "Não salvo: graph inválido (valide para ver os erros)." });
        void validate();
      } else {
        setToast({ kind: "err", msg: err instanceof Error ? err.message : "Falha ao salvar." });
      }
    }
  }

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 3500);
    return () => clearTimeout(t);
  }, [toast]);

  const selectedNode = nodes.find((n) => n.id === selNode) || null;
  const selectedEdge = edges.find((e) => e.id === selEdge) || null;
  const filteredJobs = (jobsQ.data?.items ?? []).filter((j) => !q || j.name.toLowerCase().includes(q.toLowerCase()));

  function patchNode(patch: Record<string, unknown>) {
    setNodes((nds) => nds.map((n) => (n.id === selNode ? { ...n, data: { ...n.data, ...patch } } : n)));
  }
  function patchEdge(patch: Record<string, unknown>) {
    setEdges((eds) => eds.map((e) => (e.id === selEdge ? { ...e, data: { ...e.data, ...patch } } : e)));
  }

  return (
    <div className="flex h-[70vh] gap-3">
      {/* Sidebar de jobs */}
      <div className="flex w-64 shrink-0 flex-col rounded-2xl border border-gray-200 bg-white p-3">
        <div className="relative mb-2">
          <Search size={15} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar job…" className="h-9 w-full rounded-lg border border-gray-200 pl-8 pr-2 text-sm focus:border-brand-400 focus:outline-none" />
        </div>
        <div className="scrollbar-thin flex-1 space-y-1 overflow-y-auto">
          {filteredJobs.map((j) => (
            <button key={j.id} onClick={() => canWrite && addJob(j)} disabled={!canWrite}
              className="flex w-full items-center justify-between rounded-lg border border-gray-100 px-2.5 py-2 text-left text-sm hover:border-brand-200 hover:bg-brand-50/40 disabled:opacity-50">
              <div className="min-w-0">
                <div className="truncate font-medium text-gray-800">{j.name}</div>
                <div className="text-[11px] text-gray-400">{j.type}{!j.is_active && " · inativo"}</div>
              </div>
              <Plus size={15} className="shrink-0 text-brand-500" />
            </button>
          ))}
        </div>
      </div>

      {/* Canvas */}
      <div className="relative flex-1 overflow-hidden rounded-2xl border border-gray-200 bg-slate-50">
        {toast && (
          <div className={cn("absolute left-1/2 top-3 z-20 -translate-x-1/2 rounded-lg border px-3 py-1.5 text-sm shadow-card",
            toast.kind === "ok" ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-red-200 bg-red-50 text-red-700")}>
            {toast.msg}
          </div>
        )}
        <div className="absolute right-3 top-3 z-20 flex gap-2">
          <SecondaryButton size="sm" icon={<CheckCircle2 size={15} />} onClick={validate}>Validar</SecondaryButton>
          {canWrite && <PrimaryButton size="sm" icon={<Save size={15} />} onClick={save}>Salvar</PrimaryButton>}
        </div>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodeClick={(_, n) => { setSelNode(n.id); setSelEdge(null); }}
          onEdgeClick={(_, e) => { setSelEdge(e.id); setSelNode(null); }}
          onPaneClick={() => { setSelNode(null); setSelEdge(null); }}
          fitView
          proOptions={{ hideAttribution: true }}
        >
          <Background color="#cbd5e1" gap={18} />
          <Controls showInteractive={false} />
          <MiniMap pannable zoomable className="!bg-white" />
        </ReactFlow>
      </div>

      {/* Painel de propriedades / validação */}
      <div className="flex w-72 shrink-0 flex-col gap-3">
        {(selectedNode || selectedEdge) && canWrite && (
          <div className="rounded-2xl border border-gray-200 bg-white p-4">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-gray-900">{selectedNode ? "Step" : "Conexão"}</h3>
              <button onClick={removeSelected} className="inline-flex items-center gap-1 text-xs text-red-600 hover:underline"><Trash2 size={13} /> Remover</button>
            </div>
            {selectedNode && (
              <div className="space-y-3 text-sm">
                <Field label="Nome do step">
                  <input className={inp} value={(selectedNode.data.label as string) ?? ""} onChange={(e) => patchNode({ label: e.target.value })} />
                </Field>
                <div className="text-xs text-gray-500">Job: <span className="font-medium text-gray-700">{selectedNode.data.jobName as string}</span> · {selectedNode.data.jobType as string} · {(selectedNode.data.engine as string) ?? "—"}</div>
                <Field label="Run if">
                  <select className={inp} value={(selectedNode.data.run_if as string) ?? "success"} onChange={(e) => patchNode({ run_if: e.target.value })}>
                    {["success", "finished", "failed", "always"].map((r) => <option key={r} value={r}>{r}</option>)}
                  </select>
                </Field>
                <div className="grid grid-cols-2 gap-2">
                  <Field label="Retry"><input type="number" className={inp} value={(selectedNode.data.retry_count as number) ?? 0} onChange={(e) => patchNode({ retry_count: Number(e.target.value) })} /></Field>
                  <Field label="Timeout (s)"><input type="number" className={inp} value={(selectedNode.data.timeout_seconds as number) ?? ""} onChange={(e) => patchNode({ timeout_seconds: e.target.value ? Number(e.target.value) : null })} /></Field>
                </div>
                <label className="flex items-center gap-2 text-sm text-gray-700">
                  <input type="checkbox" className="h-4 w-4 rounded border-gray-300 text-brand-500" checked={(selectedNode.data.active as boolean) ?? true} onChange={(e) => patchNode({ active: e.target.checked })} /> Ativo
                </label>
              </div>
            )}
            {selectedEdge && (
              <div className="space-y-3 text-sm">
                <div className="text-xs text-gray-500">{selectedEdge.source} → {selectedEdge.target}</div>
                <Field label="Tipo de dependência">
                  <select className={inp} value={(selectedEdge.data?.dependency_type as string) ?? "success"} onChange={(e) => patchEdge({ dependency_type: e.target.value })}>
                    {["success", "finished", "failed", "always"].map((r) => <option key={r} value={r}>{r}</option>)}
                  </select>
                </Field>
              </div>
            )}
          </div>
        )}

        {validation && (
          <div className="rounded-2xl border border-gray-200 bg-white p-4">
            <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-gray-900">
              {validation.valid ? <CheckCircle2 size={15} className="text-emerald-500" /> : <AlertTriangle size={15} className="text-red-500" />}
              Validação
            </h3>
            {validation.errors.map((e, i) => <p key={i} className="mb-1 rounded bg-red-50 px-2 py-1 text-xs text-red-700">{e}</p>)}
            {validation.warnings.map((w, i) => <p key={i} className="mb-1 rounded bg-amber-50 px-2 py-1 text-xs text-amber-700">{w}</p>)}
            {validation.valid && validation.warnings.length === 0 && <p className="text-xs text-emerald-600">Sem problemas.</p>}
          </div>
        )}

        {!selectedNode && !selectedEdge && !validation && (
          <div className="rounded-2xl border border-dashed border-gray-200 bg-white/50 p-4 text-xs text-gray-400">
            Arraste jobs da lateral para o canvas, conecte-os arrastando entre as bolinhas e clique em <b>Salvar</b>. Clique num nó ou conexão para editar.
          </div>
        )}
      </div>
    </div>
  );
}

const inp = "mt-1 w-full rounded-lg border border-gray-200 px-2.5 py-1.5 text-sm focus:border-brand-400 focus:outline-none";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <span className="text-xs font-medium text-gray-500">{label}</span>
      {children}
    </div>
  );
}
