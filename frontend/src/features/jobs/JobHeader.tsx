import { useNavigate } from "react-router-dom";
import { ArrowLeft, Pencil, Play, Trash2 } from "lucide-react";

import { PrimaryButton, SecondaryButton, StatusBadge } from "@/components/ui";
import type { JobDetail } from "@/features/jobs/types";
import { JOB_TYPE_LABEL, fmtDate } from "@/features/jobs/types";

export function JobHeader({
  job,
  canRun,
  canEdit,
  canDelete,
  running,
  onRun,
  onEdit,
  onDelete,
}: {
  job: JobDetail;
  canRun: boolean;
  canEdit: boolean;
  canDelete: boolean;
  running: boolean;
  onRun: () => void;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const navigate = useNavigate();
  return (
    <div className="mb-6">
      <button
        onClick={() => navigate("/jobs")}
        className="mb-4 inline-flex items-center gap-1.5 text-sm text-gray-500 transition-colors hover:text-gray-800"
      >
        <ArrowLeft size={16} /> Voltar para Jobs
      </button>

      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-gray-900">{job.name}</h1>
            <StatusBadge status={job.is_active ? "active" : "inactive"} />
          </div>
          {job.description && <p className="mt-1 text-sm text-gray-500">{job.description}</p>}
          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-500">
            <span className="inline-flex items-center gap-1.5">
              <span className="rounded-md bg-gray-100 px-2 py-0.5 font-medium text-gray-600">
                {JOB_TYPE_LABEL[job.type] ?? job.type}
              </span>
            </span>
            {job.engine && <span>engine: <span className="font-mono text-gray-700">{job.engine}</span></span>}
            <span className="truncate font-mono">{job.script_path ?? "—"}</span>
          </div>
          <div className="mt-1 flex flex-wrap gap-x-4 text-xs text-gray-400">
            <span>Criado em {fmtDate(job.created_at)}{job.created_by ? ` por ${job.created_by}` : ""}</span>
            <span>Atualizado em {fmtDate(job.updated_at)}</span>
          </div>
        </div>

        <div className="flex shrink-0 flex-wrap items-center gap-2">
          <SecondaryButton onClick={() => navigate("/jobs")}>Voltar</SecondaryButton>
          {canEdit && (
            <SecondaryButton icon={<Pencil size={15} />} onClick={onEdit}>Editar</SecondaryButton>
          )}
          {canDelete && (
            <button
              onClick={onDelete}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-red-200 bg-white px-4 text-sm font-semibold text-red-600 transition-colors hover:bg-red-50"
            >
              <Trash2 size={15} /> Excluir
            </button>
          )}
          {canRun && (
            <PrimaryButton icon={<Play size={16} />} loading={running} disabled={!job.is_active} onClick={onRun}>
              Executar job
            </PrimaryButton>
          )}
        </div>
      </div>
    </div>
  );
}
