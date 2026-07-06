import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { Page } from "@/lib/api";
import { DataTable, StatusBadge } from "@/components/ui/Table";

interface Cluster {
  id: number;
  name: string;
  type: string;
  spark_master_url: string | null;
  status: string;
  worker_count: number | null;
  total_cores: number | null;
  total_memory: string | null;
}

export default function ClustersPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["clusters"],
    queryFn: () => api.get<Page<Cluster>>("/api/v1/clusters?page=1&page_size=25"),
  });

  const rows = data?.items ?? [];

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-900">Clusters</h1>
      <p className="text-sm text-slate-500">Clusters Spark disponíveis para execução.</p>

      <div className="mt-6">
        <DataTable
          columns={["Nome", "Tipo", "Master URL", "Workers", "Cores", "Memória", "Status"]}
          isEmpty={!isLoading && rows.length === 0}
          empty="Nenhum cluster cadastrado. Rode o seed do cluster local."
        >
          {rows.map((c) => (
            <tr key={c.id}>
              <td className="px-4 py-3 font-medium text-slate-800">{c.name}</td>
              <td className="px-4 py-3 text-slate-600">{c.type}</td>
              <td className="px-4 py-3 font-mono text-xs text-slate-500">
                {c.spark_master_url ?? "—"}
              </td>
              <td className="px-4 py-3 text-slate-600">{c.worker_count ?? "—"}</td>
              <td className="px-4 py-3 text-slate-600">{c.total_cores ?? "—"}</td>
              <td className="px-4 py-3 text-slate-600">{c.total_memory ?? "—"}</td>
              <td className="px-4 py-3">
                <StatusBadge status={c.status} />
              </td>
            </tr>
          ))}
        </DataTable>
      </div>
    </div>
  );
}
