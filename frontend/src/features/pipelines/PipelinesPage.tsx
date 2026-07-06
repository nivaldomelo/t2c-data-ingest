import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { Page } from "@/lib/api";
import { DataTable, StatusBadge } from "@/components/ui/Table";

interface Pipeline {
  id: number;
  name: string;
  domain: string | null;
  layer: string | null;
  is_active: boolean;
  steps: { id: number }[];
}

export default function PipelinesPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["pipelines"],
    queryFn: () => api.get<Page<Pipeline>>("/api/v1/pipelines?page=1&page_size=25"),
  });

  const rows = data?.items ?? [];

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-900">Pipelines</h1>
      <p className="text-sm text-slate-500">DAGs simplificadas com múltiplos steps.</p>

      <div className="mt-6">
        <DataTable
          columns={["Nome", "Domínio", "Camada", "Steps", "Status"]}
          isEmpty={!isLoading && rows.length === 0}
          empty="Nenhum pipeline cadastrado."
        >
          {rows.map((p) => (
            <tr key={p.id}>
              <td className="px-4 py-3 font-medium text-slate-800">{p.name}</td>
              <td className="px-4 py-3 text-slate-600">{p.domain ?? "—"}</td>
              <td className="px-4 py-3 text-slate-600">{p.layer ?? "—"}</td>
              <td className="px-4 py-3 text-slate-600">{p.steps?.length ?? 0}</td>
              <td className="px-4 py-3">
                <StatusBadge status={p.is_active ? "active" : "inactive"} />
              </td>
            </tr>
          ))}
        </DataTable>
      </div>
    </div>
  );
}
