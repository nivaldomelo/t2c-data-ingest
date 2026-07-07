import { useQuery } from "@tanstack/react-query";
import { Wind } from "lucide-react";

import { api } from "@/lib/api";
import type { Page } from "@/lib/api";
import { DataTable, EmptyState, PageHeader } from "@/components/ui";
import type { Column } from "@/components/ui";

interface Dag {
  id: number;
  dag_name: string;
  schedule: string | null;
  migration_status: string;
  mapped_pipeline_id: number | null;
  tasks: { id: number }[];
}

const STATUS: Record<string, { label: string; cls: string }> = {
  nao_analisada: { label: "Não analisada", cls: "bg-gray-100 text-gray-600" },
  em_analise: { label: "Em análise", cls: "bg-sky-100 text-sky-700" },
  migracao_planejada: { label: "Migração planejada", cls: "bg-brand-100 text-brand-700" },
  migrada_parcialmente: { label: "Migrada parcialmente", cls: "bg-amber-100 text-amber-700" },
  migrada: { label: "Migrada", cls: "bg-emerald-100 text-emerald-700" },
  descontinuada: { label: "Descontinuada", cls: "bg-red-100 text-red-700" },
};

export default function AirflowPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["airflow-dags"],
    queryFn: () => api.get<Page<Dag>>("/api/v1/airflow/dags?page=1&page_size=25"),
  });

  const columns: Column<Dag>[] = [
    { key: "dag", header: "DAG", render: (d) => <span className="font-medium text-gray-900">{d.dag_name}</span> },
    { key: "schedule", header: "Schedule", render: (d) => <span className="font-mono text-xs text-gray-500">{d.schedule ?? "—"}</span> },
    { key: "tasks", header: "Tasks", align: "center", render: (d) => d.tasks?.length ?? 0 },
    { key: "pipe", header: "Pipeline", render: (d) => (d.mapped_pipeline_id ? `#${d.mapped_pipeline_id}` : "—") },
    {
      key: "status",
      header: "Migração",
      align: "right",
      render: (d) => {
        const s = STATUS[d.migration_status] ?? { label: d.migration_status, cls: "bg-gray-100 text-gray-600" };
        return <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${s.cls}`}>{s.label}</span>;
      },
    },
  ];

  return (
    <div>
      <PageHeader
        icon={<Wind size={22} />}
        title="Airflow legado"
        description="Inventário das DAGs atuais para migração gradual. As DAGs de produção não são movidas por aqui."
      />
      <DataTable
        columns={columns}
        rows={data?.items ?? []}
        rowKey={(d) => d.id}
        loading={isLoading}
        empty={
          <EmptyState
            icon={<Wind size={24} />}
            title="Nenhuma DAG inventariada"
            description="Cadastre as DAGs do Airflow atual para planejar a migração com controle."
          />
        }
      />
    </div>
  );
}
