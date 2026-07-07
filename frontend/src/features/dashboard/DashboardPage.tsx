import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  AlertTriangle,
  Boxes,
  CheckCircle2,
  Clock,
  LayoutDashboard,
  Loader2,
  PlayCircle,
  Workflow,
  XCircle,
} from "lucide-react";

import { api } from "@/lib/api";
import { Card, MetricCard, PageHeader } from "@/components/ui";
import { MetricCardSkeleton } from "@/components/ui/LoadingSkeleton";

interface Summary {
  jobs_total: number;
  pipelines_total: number;
  executions_today: number;
  executions_success_today: number;
  executions_failed_today: number;
  jobs_running: number;
  avg_duration_seconds: number | null;
}

interface Failure {
  execution_id: number;
  target_name: string | null;
  status: string;
  finished_at: string | null;
  final_message: string | null;
}

function fmtDuration(seconds: number | null): string {
  if (seconds == null) return "—";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}m ${s}s`;
}

export default function DashboardPage() {
  const summary = useQuery({
    queryKey: ["dashboard-summary"],
    queryFn: () => api.get<Summary>("/api/v1/dashboard/summary"),
  });
  const failures = useQuery({
    queryKey: ["dashboard-failures"],
    queryFn: () => api.get<Failure[]>("/api/v1/dashboard/recent-failures"),
  });

  const s = summary.data;
  const loading = summary.isLoading;

  const metrics = [
    { label: "Jobs cadastrados", value: s?.jobs_total, icon: <Boxes size={20} /> },
    { label: "Pipelines ativos", value: s?.pipelines_total, icon: <Workflow size={20} /> },
    { label: "Execuções (24h)", value: s?.executions_today, icon: <PlayCircle size={20} />, accent: true },
    { label: "Jobs em execução", value: s?.jobs_running, icon: <Loader2 size={20} />, accent: true },
    { label: "Sucesso (24h)", value: s?.executions_success_today, icon: <CheckCircle2 size={20} />, tone: "success" as const },
    { label: "Erros (24h)", value: s?.executions_failed_today, icon: <XCircle size={20} />, tone: "danger" as const },
    { label: "Tempo médio", value: fmtDuration(s?.avg_duration_seconds ?? null), icon: <Clock size={20} /> },
  ];

  return (
    <div>
      <PageHeader
        icon={<LayoutDashboard size={22} />}
        title="Dashboard"
        description="Visão executiva da plataforma de ingestão e processamento."
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {loading
          ? Array.from({ length: 7 }).map((_, i) => <MetricCardSkeleton key={i} />)
          : metrics.map((m) => (
              <MetricCard
                key={m.label}
                label={m.label}
                value={m.value ?? "—"}
                icon={m.icon}
                accent={m.accent}
                tone={m.tone}
              />
            ))}
      </div>

      <Card className="mt-8">
        <div className="flex items-center justify-between border-b border-gray-100 px-5 py-4">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-gray-900">
            <AlertTriangle size={16} className="text-brand-500" />
            Últimas falhas
          </h2>
          <Link to="/executions?status=failed" className="text-xs font-medium text-brand-600 hover:text-brand-700">
            Ver todas
          </Link>
        </div>
        <div className="divide-y divide-gray-50">
          {failures.isLoading ? (
            <div className="space-y-2 p-5">
              <div className="h-10 animate-pulse rounded-lg bg-gray-50" />
              <div className="h-10 animate-pulse rounded-lg bg-gray-50" />
            </div>
          ) : (failures.data ?? []).length === 0 ? (
            <div className="flex items-center gap-3 px-5 py-8 text-sm text-gray-400">
              <CheckCircle2 size={18} className="text-emerald-500" />
              Nenhuma falha recente. Tudo rodando bem.
            </div>
          ) : (
            (failures.data ?? []).map((f) => (
              <Link
                key={f.execution_id}
                to={`/executions/${f.execution_id}`}
                className="flex items-center justify-between px-5 py-3.5 transition-colors hover:bg-red-50/40"
              >
                <div className="flex items-center gap-3">
                  <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-red-50 text-red-500">
                    <XCircle size={16} />
                  </span>
                  <div>
                    <p className="text-sm font-medium text-gray-900">
                      #{f.execution_id} · {f.target_name ?? "—"}
                    </p>
                    <p className="text-xs text-gray-400">{f.final_message ?? f.status}</p>
                  </div>
                </div>
                <span className="text-xs text-gray-400">
                  {f.finished_at ? new Date(f.finished_at).toLocaleString("pt-BR") : ""}
                </span>
              </Link>
            ))
          )}
        </div>
      </Card>
    </div>
  );
}
