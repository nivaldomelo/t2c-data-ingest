import type { ReactNode } from "react";

import { Card, StatusBadge } from "@/components/ui";
import { TagBadges } from "@/components/ui/TagBadges";
import type { JobDetail } from "@/features/jobs/types";
import { JOB_TYPE_LABEL, fmtDate, fmtDuration } from "@/features/jobs/types";

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-gray-400">{label}</dt>
      <dd className="mt-0.5 text-sm text-gray-800">{children}</dd>
    </div>
  );
}

export function JobOverviewTab({ job }: { job: JobDetail }) {
  const params = job.default_parameters ?? {};
  const paramKeys = Object.keys(params);

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
      <Card className="p-5 lg:col-span-2">
        <h2 className="mb-4 text-sm font-semibold text-gray-900">Informações principais</h2>
        <dl className="grid grid-cols-2 gap-x-4 gap-y-4">
          <Field label="Tipo">{JOB_TYPE_LABEL[job.type] ?? job.type}</Field>
          <Field label="Engine"><span className="font-mono">{job.engine ?? "—"}</span></Field>
          <div className="col-span-2">
            <Field label="Caminho do script"><span className="font-mono text-xs">{job.script_path ?? "—"}</span></Field>
          </div>
          <Field label="Conexão origem">{job.source_connection_name ?? "—"}</Field>
          <Field label="Conexão destino">{job.target_connection_name ?? "—"}</Field>
          <Field label="Timeout">{job.timeout_seconds ? `${job.timeout_seconds}s` : "—"}</Field>
          <Field label="Retry">{job.retry_count ?? 0}</Field>
          <Field label="Criado por">{job.created_by ?? "—"}</Field>
          <Field label="Status">
            <StatusBadge status={job.is_active ? "active" : "inactive"} />
          </Field>
          <div className="col-span-2">
            <Field label="Tags"><TagBadges tags={job.tags ?? []} max={12} /></Field>
          </div>
        </dl>

        <div className="mt-5 border-t border-gray-100 pt-4">
          <dt className="text-xs font-medium uppercase tracking-wide text-gray-400">Parâmetros padrão</dt>
          {paramKeys.length === 0 ? (
            <p className="mt-1 text-sm text-gray-400">Nenhum parâmetro padrão definido.</p>
          ) : (
            <div className="mt-2 space-y-1">
              {paramKeys.map((k) => (
                <div key={k} className="flex justify-between gap-3 font-mono text-xs">
                  <span className="text-gray-500">{k}</span>
                  <span className="truncate text-gray-800">{String((params as Record<string, unknown>)[k])}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </Card>

      <Card className="p-5">
        <h2 className="mb-4 text-sm font-semibold text-gray-900">Execuções</h2>
        <dl className="space-y-4">
          <Field label="Total de execuções">{job.executions_total}</Field>
          <Field label="Última execução">
            {job.last_execution_id ? `#${job.last_execution_id} · ${fmtDate(job.last_finished_at)}` : "—"}
          </Field>
          <Field label="Último status">
            {job.last_status ? <StatusBadge status={job.last_status} /> : "—"}
          </Field>
          <Field label="Tempo médio (sucesso)">{fmtDuration(job.avg_duration_seconds)}</Field>
        </dl>
      </Card>
    </div>
  );
}
