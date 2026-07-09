import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Workflow } from "lucide-react";

import { api } from "@/lib/api";
import type { Page } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { DataTable, EmptyState, PageHeader, PrimaryButton, SecondaryButton, StatusBadge } from "@/components/ui";
import type { Column } from "@/components/ui";
import { Modal } from "@/components/ui/Modal";
import type { Pipeline } from "@/features/pipelines/types";

export default function PipelinesPage() {
  const { can } = useAuth();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [group, setGroup] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["pipelines"],
    queryFn: () => api.get<Page<Pipeline>>("/api/v1/pipelines?page=1&page_size=25"),
  });

  const create = useMutation({
    mutationFn: () => api.post<Pipeline>("/api/v1/pipelines", { name, description: description || null, group_name: group || null }),
    onSuccess: (p) => { qc.invalidateQueries({ queryKey: ["pipelines"] }); setOpen(false); navigate(`/pipelines/${p.id}`); },
    onError: (e) => setError(e instanceof Error ? e.message : "Falha ao criar"),
  });

  const columns: Column<Pipeline>[] = [
    { key: "name", header: "Pipeline", render: (p) => (
      <button onClick={(e) => { e.stopPropagation(); navigate(`/pipelines/${p.id}`); }} className="font-medium text-gray-900 hover:text-brand-600 hover:underline">{p.name}</button>
    ) },
    { key: "group", header: "Grupo", render: (p) => <span className="text-gray-600">{p.group_name ?? "—"}</span> },
    { key: "steps", header: "Jobs", align: "center", render: (p) => p.steps_count },
    { key: "active", header: "Ativo", align: "right", render: (p) => <StatusBadge status={p.is_active ? "active" : "inactive"} /> },
  ];

  const inp = "mt-1.5 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-brand-400 focus:outline-none";

  return (
    <div>
      <PageHeader
        icon={<Workflow size={22} />}
        title="Pipelines"
        description="Monte pipelines conectando jobs em uma DAG visual (Pipeline Builder)."
        actions={can("ingest:pipelines:write") ? <PrimaryButton icon={<Plus size={16} />} onClick={() => { setError(null); setName(""); setDescription(""); setGroup(""); setOpen(true); }}>Novo pipeline</PrimaryButton> : null}
      />
      <DataTable
        columns={columns}
        rows={data?.items ?? []}
        rowKey={(p) => p.id}
        loading={isLoading}
        onRowClick={(p) => navigate(`/pipelines/${p.id}`)}
        empty={<EmptyState icon={<Workflow size={24} />} title="Nenhum pipeline" description="Crie um pipeline e monte a DAG conectando jobs no builder." />}
      />

      <Modal open={open} onClose={() => setOpen(false)} title="Novo pipeline" description="Depois de criar, abra o Builder para montar a DAG."
        footer={<><SecondaryButton onClick={() => setOpen(false)}>Cancelar</SecondaryButton><PrimaryButton loading={create.isPending} disabled={!name.trim()} onClick={() => create.mutate()}>Criar e abrir builder</PrimaryButton></>}>
        {error && <div className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}
        <div className="space-y-3">
          <div><label className="text-sm font-medium text-gray-700">Nome *</label><input className={inp} value={name} onChange={(e) => setName(e.target.value)} placeholder="pipeline_massa_teste_postgres_to_mysql" /></div>
          <div><label className="text-sm font-medium text-gray-700">Descrição</label><input className={inp} value={description} onChange={(e) => setDescription(e.target.value)} /></div>
          <div><label className="text-sm font-medium text-gray-700">Grupo</label><input className={inp} value={group} onChange={(e) => setGroup(e.target.value)} placeholder="massa_teste" /></div>
        </div>
      </Modal>
    </div>
  );
}
