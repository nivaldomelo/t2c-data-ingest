import { Handle, Position } from "@xyflow/react";
import type { NodeProps } from "@xyflow/react";
import { Boxes, Zap } from "lucide-react";

import { cn } from "@/lib/cn";

export interface JobNodeData {
  label: string;
  jobName: string;
  jobType: string;
  engine: string | null;
  active: boolean;
  status?: string | null; // execution status overlay (optional)
  [key: string]: unknown;
}

const STATUS_RING: Record<string, string> = {
  success: "ring-emerald-400",
  failed: "ring-red-400",
  running: "ring-brand-400",
  skipped: "ring-gray-300",
};

export function PipelineJobNode({ data, selected }: NodeProps) {
  const d = data as JobNodeData;
  const isSpark = d.jobType?.startsWith("spark");
  const ring = d.status ? STATUS_RING[d.status] ?? "ring-gray-200" : "ring-transparent";
  return (
    <div
      className={cn(
        "w-56 rounded-xl border bg-white shadow-card ring-2 transition-shadow",
        selected ? "border-brand-400" : "border-gray-200",
        ring,
        !d.active && "opacity-60"
      )}
    >
      <Handle type="target" position={Position.Left} className="!h-2 !w-2 !bg-gray-400" />
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
        <span className={cn("font-medium", d.active ? "text-emerald-600" : "text-gray-400")}>
          {d.active ? "Ativo" : "Inativo"}
        </span>
      </div>
      <Handle type="source" position={Position.Right} className="!h-2 !w-2 !bg-brand-500" />
    </div>
  );
}
