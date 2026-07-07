import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Boxes, Play } from "lucide-react";

import { api } from "@/lib/api";
import type { Page } from "@/lib/api";
import { DataTable, EmptyState, PageHeader, PrimaryButton, StatusBadge } from "@/components/ui";
import type { Column } from "@/components/ui";
import { useAuth } from "@/lib/auth";

interface Job {
  id: number;
  name: string;
  description: string | null;
  type: string;
  script_path: string | null;
  is_active: boolean;
}

const TYPE_LABEL: Record<string, string> = {
  python: "Python",
  spark_python: "Spark · Python",
  spark_sql: "Spark · SQL",
  spark_submit: "Spark · Submit",
};

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

  const columns: Column<Job>[] = [
    {
      key: "name",
      header: "Job",
      render: (j) => (
        <div>
          <div className="font-medium text-gray-900">{j.name}</div>
          <div className="font-mono text-xs text-gray-400">{j.script_path ?? "—"}</div>
        </div>
      ),
    },
    {
      key: "type",
      header: "Tipo",
      render: (j) => (
        <span className="inline-flex rounded-md bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600">
          {TYPE_LABEL[j.type] ?? j.type}
        </span>
      ),
    },
    { key: "status", header: "Status", render: (j) => <StatusBadge status={j.is_active ? "active" : "inactive"} /> },
    {
      key: "actions",
      header: "",
      align: "right",
      render: (j) =>
        can("ingest:run") ? (
          <PrimaryButton
            size="sm"
            icon={<Play size={14} />}
            loading={run.isPending && run.variables === j.id}
            disabled={!j.is_active}
            onClick={() => run.mutate(j.id)}
          >
            Executar
          </PrimaryButton>
        ) : null,
    },
  ];

  return (
    <div>
      <PageHeader
        icon={<Boxes size={22} />}
        title="Jobs"
        description="Jobs Python e Spark cadastrados na plataforma."
      />
      <DataTable
        columns={columns}
        rows={data?.items ?? []}
        rowKey={(j) => j.id}
        loading={isLoading}
        empty={
          <EmptyState
            icon={<Boxes size={24} />}
            title="Nenhum job cadastrado"
            description="Cadastre um job Python ou Spark para começar a executar ingestões."
          />
        }
      />
    </div>
  );
}
