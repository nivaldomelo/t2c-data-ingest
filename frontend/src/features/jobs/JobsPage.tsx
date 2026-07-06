import { useQueryClient, useQuery, useMutation } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { Page } from "@/lib/api";
import { DataTable, StatusBadge } from "@/components/ui/Table";
import { useAuth } from "@/lib/auth";

interface Job {
  id: number;
  name: string;
  type: string;
  script_path: string | null;
  is_active: boolean;
}

export default function JobsPage() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["jobs"],
    queryFn: () => api.get<Page<Job>>("/api/v1/jobs?page=1&page_size=25"),
  });

  const run = useMutation({
    mutationFn: (jobId: number) => api.post(`/api/v1/jobs/${jobId}/run`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["executions"] }),
  });

  const rows = data?.items ?? [];

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-900">Jobs</h1>
      <p className="text-sm text-slate-500">Jobs Python e Spark cadastrados.</p>

      <div className="mt-6">
        <DataTable
          columns={["Nome", "Tipo", "Script", "Status", "Ações"]}
          isEmpty={!isLoading && rows.length === 0}
          empty="Nenhum job cadastrado."
        >
          {rows.map((j) => (
            <tr key={j.id}>
              <td className="px-4 py-3 font-medium text-slate-800">{j.name}</td>
              <td className="px-4 py-3 text-slate-600">{j.type}</td>
              <td className="px-4 py-3 font-mono text-xs text-slate-500">{j.script_path ?? "—"}</td>
              <td className="px-4 py-3">
                <StatusBadge status={j.is_active ? "active" : "inactive"} />
              </td>
              <td className="px-4 py-3">
                {can("ingest:run") && (
                  <button
                    onClick={() => run.mutate(j.id)}
                    disabled={run.isPending || !j.is_active}
                    className="rounded-lg bg-brand-600 px-3 py-1 text-xs font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
                  >
                    Executar
                  </button>
                )}
              </td>
            </tr>
          ))}
        </DataTable>
      </div>
    </div>
  );
}
