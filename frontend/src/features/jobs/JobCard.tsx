import { useEffect, useRef, useState } from "react";
import {
  ArrowRight, Code2, Flame, MoreVertical, Pencil, Play, Trash2,
} from "lucide-react";

import { cn } from "@/lib/cn";
import { fmtDuration } from "@/features/jobs/types";

export interface JobCardData {
  id: number;
  name: string;
  description: string | null;
  type: string;
  job_type_label: string;
  engine: string | null;
  engine_label: string;
  engine_kind: string;
  is_active: boolean;
  source_connection_name: string | null;
  target_connection_name: string | null;
  tags: { id: number; name: string; slug: string; color: string | null }[];
  last_execution: { id: number; status: string; started_at: string | null; duration_seconds: number | null } | null;
  avg_success_duration_seconds: number | null;
}

const EXEC_TONE: Record<string, string> = {
  success: "text-emerald-600", failed: "text-red-600", timeout: "text-amber-600",
  running: "text-brand-600", queued: "text-sky-600", cancelled: "text-gray-500",
};
const EXEC_LABEL: Record<string, string> = {
  success: "Sucesso", failed: "Falha", timeout: "Timeout", running: "Em execução",
  queued: "Na fila", cancelled: "Cancelado", skipped: "Ignorado",
};

function fmtWhen(t: string | null): string {
  return t ? new Date(t).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "";
}

export function JobEngineIcon({ kind }: { kind: string }) {
  const spark = kind === "spark";
  return (
    <span className={cn("inline-flex h-8 w-8 items-center justify-center rounded-lg",
      spark ? "bg-brand-50 text-brand-600" : "bg-sky-50 text-sky-600")}>
      {spark ? <Flame size={17} /> : <Code2 size={17} />}
    </span>
  );
}

export function JobCard({
  job, canRun, canEdit, canDelete, canCode, running,
  onOpen, onRun, onCode, onEdit, onDelete,
}: {
  job: JobCardData;
  canRun: boolean; canEdit: boolean; canDelete: boolean; canCode: boolean; running: boolean;
  onOpen: () => void; onRun: () => void; onCode: () => void; onEdit: () => void; onDelete: () => void;
}) {
  const spark = job.engine_kind === "spark";
  const [menu, setMenu] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!menu) return;
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setMenu(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, [menu]);

  const le = job.last_execution;
  const visibleTags = job.tags.slice(0, 3);
  const extra = job.tags.length - visibleTags.length;

  return (
    <div className={cn(
      "group relative flex flex-col overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-card transition-shadow hover:shadow-card-hover",
      "before:absolute before:inset-x-0 before:top-0 before:h-1", spark ? "before:bg-brand-500" : "before:bg-sky-500"
    )}>
      <div className="flex flex-1 flex-col p-4 pt-5">
        {/* header */}
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2">
            <JobEngineIcon kind={job.engine_kind} />
            <span className={cn("text-xs font-semibold uppercase tracking-wide", spark ? "text-brand-600" : "text-sky-600")}>{job.engine_label}</span>
          </div>
          <span className={cn("inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium",
            job.is_active ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-gray-200 bg-gray-100 text-gray-500")}>
            <span className={cn("h-1.5 w-1.5 rounded-full", job.is_active ? "bg-emerald-500" : "bg-gray-400")} />
            {job.is_active ? "Ativo" : "Inativo"}
          </span>
        </div>

        {/* name + description */}
        <button onClick={onOpen} className="mt-3 text-left">
          <h3 className="line-clamp-1 font-mono text-sm font-semibold text-gray-900 hover:text-brand-600">{job.name}</h3>
        </button>
        <p className="mt-1 line-clamp-2 min-h-[2.5rem] text-xs text-gray-500">{job.description || "Sem descrição."}</p>

        {/* type · engine + connections */}
        <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs text-gray-500">
          <span className="rounded bg-gray-100 px-1.5 py-0.5 font-medium text-gray-600">{job.job_type_label}</span>
          {job.engine && <span className="font-mono text-gray-400">{job.engine}</span>}
        </div>
        {(job.source_connection_name || job.target_connection_name) && (
          <p className="mt-1.5 truncate font-mono text-xs text-gray-400">
            {job.source_connection_name ?? "—"} <ArrowRight size={11} className="inline" /> {job.target_connection_name ?? "—"}
          </p>
        )}

        {/* tags */}
        {job.tags.length > 0 && (
          <div className="mt-2.5 flex flex-wrap items-center gap-1">
            {visibleTags.map((t) => (
              <span key={t.id} className="rounded-full bg-gray-100 px-2 py-0.5 text-[11px] font-medium text-gray-600">{t.name}</span>
            ))}
            {extra > 0 && <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[11px] font-medium text-gray-400" title={job.tags.map((t) => t.name).join(", ")}>+{extra}</span>}
          </div>
        )}

        {/* last execution */}
        <div className="mt-3 border-t border-gray-50 pt-2.5 text-xs">
          {le ? (
            <span className="text-gray-500">
              Última execução: <span className={cn("font-medium", EXEC_TONE[le.status] ?? "text-gray-600")}>{EXEC_LABEL[le.status] ?? le.status}</span>
              {le.started_at ? ` · ${fmtWhen(le.started_at)}` : ""}
              {job.avg_success_duration_seconds != null ? ` · média ${fmtDuration(job.avg_success_duration_seconds)}` : ""}
            </span>
          ) : (
            <span className="text-gray-400">Nenhuma execução</span>
          )}
        </div>
      </div>

      {/* actions footer */}
      <div className="flex items-center gap-2 border-t border-gray-100 bg-gray-50/40 px-4 py-2.5">
        <button onClick={onOpen} className="inline-flex h-8 flex-1 items-center justify-center gap-1.5 rounded-lg bg-brand-500 px-3 text-xs font-semibold text-white transition-colors hover:bg-brand-600">
          Abrir
        </button>
        {canRun && (
          <button onClick={onRun} disabled={!job.is_active || running}
            className="inline-flex h-8 items-center justify-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 text-xs font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:opacity-50">
            <Play size={13} /> {running ? "…" : "Executar"}
          </button>
        )}
        <div ref={ref} className="relative">
          <button onClick={() => setMenu((v) => !v)} className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-gray-200 bg-white text-gray-500 hover:bg-gray-50">
            <MoreVertical size={15} />
          </button>
          {menu && (
            <div className="absolute bottom-9 right-0 z-20 w-44 overflow-hidden rounded-xl border border-gray-200 bg-white py-1 shadow-card-hover">
              {canCode && <MenuItem icon={<Code2 size={14} />} label="Abrir código" onClick={() => { setMenu(false); onCode(); }} />}
              {canEdit && <MenuItem icon={<Pencil size={14} />} label="Editar" onClick={() => { setMenu(false); onEdit(); }} />}
              {canDelete && <MenuItem icon={<Trash2 size={14} />} label="Excluir" danger onClick={() => { setMenu(false); onDelete(); }} />}
              {!canCode && !canEdit && !canDelete && <div className="px-3 py-2 text-xs text-gray-400">Sem ações</div>}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function MenuItem({ icon, label, onClick, danger }: { icon: React.ReactNode; label: string; onClick: () => void; danger?: boolean }) {
  return (
    <button onClick={onClick} className={cn("flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-gray-50",
      danger ? "text-red-600 hover:bg-red-50" : "text-gray-700")}>
      {icon} {label}
    </button>
  );
}
