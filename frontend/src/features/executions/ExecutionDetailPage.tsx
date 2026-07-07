import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Ban, Clock, Cpu, Timer, User } from "lucide-react";

import { api } from "@/lib/api";
import {
  Card,
  ExecutionTimeline,
  LogViewer,
  SecondaryButton,
  StatusBadge,
} from "@/components/ui";
import type { LogLine, TimelineStep } from "@/components/ui";
import { Skeleton } from "@/components/ui/LoadingSkeleton";
import { useAuth } from "@/lib/auth";

interface Detail {
  id: number;
  target_type: string;
  target_name: string | null;
  job_type: string | null;
  status: string;
  engine: string | null;
  triggered_by: string | null;
  queued_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  duration_seconds: number | null;
  final_message: string | null;
  error_trace: string | null;
  parameters: Record<string, unknown> | null;
  logs: LogLine[];
  runtime_parameters: { id: number; key: string; value: string | null }[];
}

function fmtDur(s: number | null): string {
  if (s == null) return "—";
  if (s < 60) return `${s}s`;
  return `${Math.floor(s / 60)}m ${s % 60}s`;
}

function fmtTime(t: string | null): string {
  return t ? new Date(t).toLocaleString("pt-BR") : "—";
}

export default function ExecutionDetailPage() {
  const { id } = useParams();
  const qc = useQueryClient();
  const { can } = useAuth();

  const { data, isLoading } = useQuery({
    queryKey: ["execution", id],
    queryFn: () => api.get<Detail>(`/api/v1/executions/${id}`),
    refetchInterval: (q) =>
      ["queued", "running"].includes((q.state.data as Detail | undefined)?.status ?? "") ? 3000 : false,
  });

  const cancel = useMutation({
    mutationFn: () => api.post(`/api/v1/executions/${id}/cancel`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["execution", id] }),
  });

  if (isLoading || !data) {
    return (
      <div>
        <Skeleton className="h-6 w-40" />
        <div className="mt-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-24 rounded-2xl" />
          ))}
        </div>
        <Skeleton className="mt-6 h-72 rounded-2xl" />
      </div>
    );
  }

  // Single-target execution -> a one-step timeline reflecting the lifecycle.
  const steps: TimelineStep[] = [
    {
      id: "exec",
      title: data.target_name ?? `Execução #${data.id}`,
      subtitle: `${data.engine ?? "—"} · ${data.job_type ?? data.target_type}`,
      status: data.status,
      meta: <StatusBadge status={data.status} />,
    },
  ];

  const summary = [
    { label: "Status", node: <StatusBadge status={data.status} />, icon: <Clock size={16} /> },
    { label: "Engine", node: <span className="font-mono text-sm text-gray-800">{data.engine ?? "—"}</span>, icon: <Cpu size={16} /> },
    { label: "Duração", node: <span className="text-sm font-semibold text-gray-900">{fmtDur(data.duration_seconds)}</span>, icon: <Timer size={16} /> },
    { label: "Disparado por", node: <span className="text-sm text-gray-800">{data.triggered_by ?? "—"}</span>, icon: <User size={16} /> },
  ];

  const isError = ["failed", "timeout"].includes(data.status);

  return (
    <div>
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <Link
            to="/executions"
            className="flex h-9 w-9 items-center justify-center rounded-lg border border-gray-200 bg-white text-gray-500 transition-colors hover:bg-gray-50 hover:text-gray-900"
          >
            <ArrowLeft size={18} />
          </Link>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold tracking-tight text-gray-900">
                {data.target_name ?? `Execução #${data.id}`}
              </h1>
              <StatusBadge status={data.status} />
            </div>
            <p className="mt-0.5 font-mono text-xs text-gray-400">
              #{data.id} · {data.target_type}
            </p>
          </div>
        </div>
        {can("ingest:run") && ["queued", "running"].includes(data.status) && (
          <SecondaryButton icon={<Ban size={16} />} loading={cancel.isPending} onClick={() => cancel.mutate()}>
            Cancelar execução
          </SecondaryButton>
        )}
      </div>

      {/* Cards de resumo */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {summary.map((s) => (
          <Card key={s.label} className="p-4">
            <div className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-gray-500">
              <span className="text-gray-400">{s.icon}</span>
              {s.label}
            </div>
            <div className="mt-2">{s.node}</div>
          </Card>
        ))}
      </div>

      {/* Destaque de erro */}
      {isError && data.final_message && (
        <div className="mt-6 rounded-2xl border border-red-200 bg-red-50 p-4">
          <p className="text-sm font-semibold text-red-800">Falha na execução</p>
          <p className="mt-1 text-sm text-red-700">{data.final_message}</p>
          {data.error_trace && (
            <pre className="mt-3 overflow-x-auto rounded-lg bg-red-100/60 p-3 font-mono text-xs text-red-800">
              {data.error_trace}
            </pre>
          )}
        </div>
      )}

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-1">
          <Card className="p-5">
            <h2 className="mb-4 text-sm font-semibold text-gray-900">Linha do tempo</h2>
            <ExecutionTimeline steps={steps} />

            <div className="mt-6 space-y-2 border-t border-gray-100 pt-4 text-xs">
              <Row label="Enfileirado" value={fmtTime(data.queued_at)} />
              <Row label="Início" value={fmtTime(data.started_at)} />
              <Row label="Fim" value={fmtTime(data.finished_at)} />
            </div>

            {data.runtime_parameters.length > 0 && (
              <div className="mt-6 border-t border-gray-100 pt-4">
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">
                  Parâmetros
                </h3>
                <div className="space-y-1">
                  {data.runtime_parameters.map((p) => (
                    <div key={p.id} className="flex justify-between gap-2 font-mono text-xs">
                      <span className="text-gray-500">{p.key}</span>
                      <span className="truncate text-gray-800">{p.value ?? "—"}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </Card>
        </div>

        <div className="lg:col-span-2">
          <LogViewer lines={data.logs} title="Logs da execução" />
        </div>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-gray-500">{label}</span>
      <span className="text-gray-800">{value}</span>
    </div>
  );
}
