import { useQuery } from "@tanstack/react-query";
import { Workflow } from "lucide-react";

import { api } from "@/lib/api";
import type { Page } from "@/lib/api";
import { DataTable, EmptyState, PageHeader, StatusBadge } from "@/components/ui";
import type { Column } from "@/components/ui";

interface Pipeline {
  id: number;
  name: string;
  domain: string | null;
  layer: string | null;
  is_active: boolean;
  steps: { id: number }[];
}

const LAYER_TONE: Record<string, string> = {
  bronze: "bg-amber-100 text-amber-700",
  silver: "bg-slate-200 text-slate-700",
  gold: "bg-yellow-100 text-yellow-700",
  full: "bg-brand-100 text-brand-700",
};

export default function PipelinesPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["pipelines"],
    queryFn: () => api.get<Page<Pipeline>>("/api/v1/pipelines?page=1&page_size=25"),
  });

  const columns: Column<Pipeline>[] = [
    { key: "name", header: "Pipeline", render: (p) => <span className="font-medium text-gray-900">{p.name}</span> },
    { key: "domain", header: "Domínio", render: (p) => <span className="text-gray-600">{p.domain ?? "—"}</span> },
    {
      key: "layer",
      header: "Camada",
      render: (p) =>
        p.layer ? (
          <span className={`inline-flex rounded-md px-2 py-0.5 text-xs font-medium capitalize ${LAYER_TONE[p.layer] ?? "bg-gray-100 text-gray-600"}`}>
            {p.layer}
          </span>
        ) : (
          "—"
        ),
    },
    { key: "steps", header: "Steps", align: "center", render: (p) => p.steps?.length ?? 0 },
    { key: "status", header: "Status", align: "right", render: (p) => <StatusBadge status={p.is_active ? "active" : "inactive"} /> },
  ];

  return (
    <div>
      <PageHeader
        icon={<Workflow size={22} />}
        title="Pipelines"
        description="DAGs simplificadas com múltiplos steps (bronze → silver → gold)."
      />
      <DataTable
        columns={columns}
        rows={data?.items ?? []}
        rowKey={(p) => p.id}
        loading={isLoading}
        empty={
          <EmptyState
            icon={<Workflow size={24} />}
            title="Nenhum pipeline cadastrado"
            description="Crie um pipeline encadeando jobs em steps ordenados."
          />
        }
      />
    </div>
  );
}
