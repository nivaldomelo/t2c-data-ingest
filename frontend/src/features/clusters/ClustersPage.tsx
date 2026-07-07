import { useQuery } from "@tanstack/react-query";
import { Server } from "lucide-react";

import { api } from "@/lib/api";
import type { Page } from "@/lib/api";
import { DataTable, EmptyState, PageHeader, StatusBadge } from "@/components/ui";
import type { Column } from "@/components/ui";

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

  const columns: Column<Cluster>[] = [
    {
      key: "name",
      header: "Cluster",
      render: (c) => (
        <div>
          <div className="font-medium text-gray-900">{c.name}</div>
          <div className="font-mono text-xs text-gray-400">{c.spark_master_url ?? "—"}</div>
        </div>
      ),
    },
    { key: "type", header: "Tipo", render: (c) => <span className="text-gray-600">{c.type}</span> },
    { key: "workers", header: "Workers", align: "center", render: (c) => c.worker_count ?? "—" },
    { key: "cores", header: "Cores", align: "center", render: (c) => c.total_cores ?? "—" },
    { key: "mem", header: "Memória", align: "center", render: (c) => c.total_memory ?? "—" },
    { key: "status", header: "Status", align: "right", render: (c) => <StatusBadge status={c.status} /> },
  ];

  return (
    <div>
      <PageHeader
        icon={<Server size={22} />}
        title="Clusters"
        description="Clusters Spark disponíveis para execução de jobs."
      />
      <DataTable
        columns={columns}
        rows={data?.items ?? []}
        rowKey={(c) => c.id}
        loading={isLoading}
        empty={
          <EmptyState
            icon={<Server size={24} />}
            title="Nenhum cluster cadastrado"
            description="Rode o seed do cluster local ou cadastre um novo cluster Spark."
          />
        }
      />
    </div>
  );
}
