import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { Card, StatCard } from "@/components/ui/Table";

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

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-900">Dashboard</h1>
      <p className="text-sm text-slate-500">Visão geral da plataforma de ingestão.</p>

      <div className="mt-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Jobs cadastrados" value={s?.jobs_total ?? "—"} />
        <StatCard label="Pipelines cadastrados" value={s?.pipelines_total ?? "—"} />
        <StatCard label="Execuções (24h)" value={s?.executions_today ?? "—"} />
        <StatCard label="Jobs em execução" value={s?.jobs_running ?? "—"} />
        <StatCard label="Sucesso (24h)" value={s?.executions_success_today ?? "—"} />
        <StatCard label="Erros (24h)" value={s?.executions_failed_today ?? "—"} />
        <StatCard
          label="Tempo médio (s)"
          value={s?.avg_duration_seconds ? Math.round(s.avg_duration_seconds) : "—"}
        />
      </div>

      <Card className="mt-8 p-5">
        <h2 className="text-sm font-semibold text-slate-700">Últimas falhas</h2>
        <div className="mt-3 space-y-2">
          {(failures.data ?? []).length === 0 && (
            <div className="text-sm text-slate-400">Nenhuma falha recente. 🎉</div>
          )}
          {(failures.data ?? []).map((f) => (
            <div
              key={f.execution_id}
              className="flex items-center justify-between rounded-lg bg-red-50 px-3 py-2 text-sm"
            >
              <span className="font-medium text-red-800">
                #{f.execution_id} · {f.target_name ?? "—"}
              </span>
              <span className="text-red-600">{f.final_message ?? f.status}</span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
