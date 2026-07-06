import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { Page } from "@/lib/api";
import { DataTable } from "@/components/ui/Table";

interface Dag {
  id: number;
  dag_name: string;
  schedule: string | null;
  migration_status: string;
  mapped_pipeline_id: number | null;
  tasks: { id: number }[];
}

const STATUS_LABEL: Record<string, string> = {
  nao_analisada: "Não analisada",
  em_analise: "Em análise",
  migracao_planejada: "Migração planejada",
  migrada_parcialmente: "Migrada parcialmente",
  migrada: "Migrada",
  descontinuada: "Descontinuada",
};

export default function AirflowPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["airflow-dags"],
    queryFn: () => api.get<Page<Dag>>("/api/v1/airflow/dags?page=1&page_size=25"),
  });

  const rows = data?.items ?? [];

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-900">Airflow legado</h1>
      <p className="text-sm text-slate-500">
        Inventário das DAGs atuais para migração gradual. As DAGs de produção não são movidas
        por aqui.
      </p>

      <div className="mt-6">
        <DataTable
          columns={["DAG", "Schedule", "Tasks", "Pipeline mapeado", "Status de migração"]}
          isEmpty={!isLoading && rows.length === 0}
          empty="Nenhuma DAG inventariada."
        >
          {rows.map((d) => (
            <tr key={d.id}>
              <td className="px-4 py-3 font-medium text-slate-800">{d.dag_name}</td>
              <td className="px-4 py-3 font-mono text-xs text-slate-500">{d.schedule ?? "—"}</td>
              <td className="px-4 py-3 text-slate-600">{d.tasks?.length ?? 0}</td>
              <td className="px-4 py-3 text-slate-600">
                {d.mapped_pipeline_id ? `#${d.mapped_pipeline_id}` : "—"}
              </td>
              <td className="px-4 py-3 text-slate-600">
                {STATUS_LABEL[d.migration_status] ?? d.migration_status}
              </td>
            </tr>
          ))}
        </DataTable>
      </div>
    </div>
  );
}
