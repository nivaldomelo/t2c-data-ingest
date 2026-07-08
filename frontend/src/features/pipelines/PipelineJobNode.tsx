import { Handle, Position } from "@xyflow/react";
import type { NodeProps } from "@xyflow/react";
import { Boxes, Plus, Zap } from "lucide-react";

import { cn } from "@/lib/cn";

export interface JobNodeData {
  label: string;
  jobName: string;
  jobType: string;
  engine: string | null;
  active: boolean;
  status?: string | null; // execution status overlay
  durationSeconds?: number | null;
  onQuickAdd?: (nodeId: string) => void;
  [key: string]: unknown;
}

// Node color scheme by execution status (edit mode = neutral white).
const STATUS: Record<string, { border: string; badge: string; label: string; pulse?: boolean }> = {
  queued: { border: "border-gray-300", badge: "bg-gray-100 text-gray-600", label: "Na fila" },
  pending: { border: "border-gray-300", badge: "bg-gray-100 text-gray-600", label: "Aguardando" },
  running: { border: "border-brand-400", badge: "bg-brand-100 text-brand-700", label: "Executando", pulse: true },
  success: { border: "border-emerald-400", badge: "bg-emerald-100 text-emerald-700", label: "Sucesso" },
  failed: { border: "border-red-400", badge: "bg-red-100 text-red-700", label: "Falhou" },
  timeout: { border: "border-amber-400", badge: "bg-amber-100 text-amber-700", label: "Timeout" },
  skipped: { border: "border-gray-200", badge: "bg-gray-50 text-gray-400", label: "Ignorado" },
  cancelled: { border: "border-gray-400", badge: "bg-gray-200 text-gray-600", label: "Cancelado" },
};

export function PipelineJobNode({ id, data, selected }: NodeProps) {
  const d = data as JobNodeData;
  const isSpark = d.jobType?.startsWith("spark");
  const st = d.status ? STATUS[d.status] : null;

  return (
    <div
      className={cn(
        "group w-56 rounded-xl border-2 bg-white shadow-card transition-all",
        selected ? "border-brand-500 ring-2 ring-brand-500/20" : st ? st.border : "border-gray-200",
        st?.pulse && "animate-pulse",
        !d.active && "opacity-60"
      )}
    >
      <Handle type="target" position={Position.Left} className="!h-2.5 !w-2.5 !border-2 !border-white !bg-gray-400" />
      <div className="flex items-center gap-2 border-b border-gray-100 px-3 py-2">
        <span className={cn("flex h-7 w-7 items-center justify-center rounded-lg", isSpark ? "bg-brand-50 text-brand-600" : "bg-slate-100 text-slate-600")}>
          {isSpark ? <Zap size={15} /> : <Boxes size={15} />}
        </span>
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold text-gray-900">{d.label}</div>
          <div className="truncate text-[11px] text-gray-400">{d.jobName}</div>
        </div>
      </div>
      <div className="flex items-center justify-between px-3 py-1.5 text-[11px]">
        <span className="rounded bg-gray-100 px-1.5 py-0.5 font-medium text-gray-600">{d.jobType}</span>
        {st ? (
          <span className={cn("rounded px-1.5 py-0.5 font-medium", st.badge)}>
            {st.label}{d.durationSeconds != null ? ` · ${d.durationSeconds}s` : ""}
          </span>
        ) : (
          <span className={cn("font-medium", d.active ? "text-emerald-600" : "text-gray-400")}>{d.active ? "Ativo" : "Inativo"}</span>
        )}
      </div>
      <Handle type="source" position={Position.Right} className="!h-2.5 !w-2.5 !border-2 !border-white !bg-brand-500" />

      {/* Quick "add next job" button (edit mode). */}
      {d.onQuickAdd && (
        <button
          title="Adicionar próximo job"
          onClick={(e) => { e.stopPropagation(); d.onQuickAdd?.(id); }}
          className="absolute -right-3 top-1/2 z-10 hidden h-6 w-6 -translate-y-1/2 items-center justify-center rounded-full bg-brand-500 text-white shadow-glow hover:bg-brand-600 group-hover:flex"
        >
          <Plus size={14} />
        </button>
      )}
    </div>
  );
}
