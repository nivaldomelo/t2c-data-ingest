import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Trash2, Workflow } from "lucide-react";

import { api } from "@/lib/api";
import type { Page } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { DataTable, EmptyState, PageHeader, PrimaryButton, SecondaryButton, StatusBadge } from "@/components/ui";
import type { Column } from "@/components/ui";
import { Modal } from "@/components/ui/Modal";
import type { Pipeline } from "@/features/pipelines/types";

type FormState = { name: string; description: string; group: string; active: boolean };
const EMPTY: FormState = { name: "", description: "", group: "", active: true };

export default function PipelinesPage() {
  const { can } = useAuth();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const canWrite = can("ingest:pipelines:write");
  const canDelete = can("ingest:pipelines:delete");

  // Modal de criar/editar. `editing` = null → criar; um Pipeline → editar.
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Pipeline | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<Pipeline | null>(null);
  const [delError, setDelError] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["pipelines"],
    queryFn: () => api.get<Page<Pipeline>>("/api/v1/pipelines?page=1&page_size=25"),
  });

  function openCreate() {
    setEditing(null); setForm(EMPTY); setError(null); setOpen(true);
  }
  function openEdit(p: Pipeline) {
    setEditing(p);
    setForm({ name: p.name, description: p.description ?? "", group: p.group_name ?? "", active: p.is_active });
    setError(null); setOpen(true);
  }

  const save = useMutation({
    mutationFn: () => {
      const body = {
        name: form.name,
        description: form.description || null,
        group_name: form.group || null,
        ...(editing ? { is_active: form.active } : {}),
      };
      return editing
        ? api.put<Pipeline>(`/api/v1/pipelines/${editing.id}`, body)
        : api.post<Pipeline>("/api/v1/pipelines", body);
    },
    onSuccess: (p) => {
      qc.invalidateQueries({ queryKey: ["pipelines"] });
      const wasCreating = !editing;
      setOpen(false);
      if (wasCreating) navigate(`/pipelines/${p.id}`);
    },
    onError: (e) => setError(e instanceof Error ? e.message : "Falha ao salvar"),
  });

  const del = useMutation({
    mutationFn: (id: number) => api.del(`/api/v1/pipelines/${id}`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["pipelines"] }); setDeleting(null); },
    onError: (e) => setDelError(e instanceof Error ? e.message : "Falha ao excluir"),
  });

  const columns: Column<Pipeline>[] = [
    { key: "name", header: "Pipeline", render: (p) => (
      <button onClick={(e) => { e.stopPropagation(); navigate(`/pipelines/${p.id}`); }} className="font-medium text-gray-900 hover:text-brand-600 hover:underline">{p.name}</button>
    ) },
    { key: "group", header: "Grupo", render: (p) => <span className="text-gray-600">{p.group_name ?? "—"}</span> },
    { key: "steps", header: "Jobs", align: "center", render: (p) => p.steps_count },
    { key: "active", header: "Ativo", align: "center", render: (p) => <StatusBadge status={p.is_active ? "active" : "inactive"} /> },
  ];
  if (canWrite || canDelete) {
    columns.push({
      key: "actions", header: "Ações", align: "right", render: (p) => (
        <div className="flex items-center justify-end gap-1" onClick={(e) => e.stopPropagation()}>
          {canWrite && (
            <button onClick={() => openEdit(p)} title="Editar"
              className="rounded-lg p-1.5 text-gray-500 hover:bg-gray-100 hover:text-brand-600"><Pencil size={16} /></button>
          )}
          {canDelete && (
            <button onClick={() => { setDelError(null); setDeleting(p); }} title="Excluir"
              className="rounded-lg p-1.5 text-gray-500 hover:bg-red-50 hover:text-red-600"><Trash2 size={16} /></button>
          )}
        </div>
      ),
    });
  }

  const inp = "mt-1.5 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-brand-400 focus:outline-none";

  return (
    <div>
      <PageHeader
        icon={<Workflow size={22} />}
        title="Pipelines"
        description="Monte pipelines conectando jobs em uma DAG visual (Pipeline Builder)."
        actions={canWrite ? <PrimaryButton icon={<Plus size={16} />} onClick={openCreate}>Novo pipeline</PrimaryButton> : null}
      />
      <DataTable
        columns={columns}
        rows={data?.items ?? []}
        rowKey={(p) => p.id}
        loading={isLoading}
        onRowClick={(p) => navigate(`/pipelines/${p.id}`)}
        empty={<EmptyState icon={<Workflow size={24} />} title="Nenhum pipeline" description="Crie um pipeline e monte a DAG conectando jobs no builder." />}
      />

      {/* Criar / editar */}
      <Modal open={open} onClose={() => setOpen(false)}
        title={editing ? "Editar pipeline" : "Novo pipeline"}
        description={editing ? "Altere o nome, a descrição, o grupo ou o status do pipeline." : "Depois de criar, abra o Builder para montar a DAG."}
        footer={<><SecondaryButton onClick={() => setOpen(false)}>Cancelar</SecondaryButton><PrimaryButton loading={save.isPending} disabled={!form.name.trim()} onClick={() => save.mutate()}>{editing ? "Salvar" : "Criar e abrir builder"}</PrimaryButton></>}>
        {error && <div className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}
        <div className="space-y-3">
          <div><label className="text-sm font-medium text-gray-700">Nome *</label><input className={inp} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="pipeline_massa_teste_postgres_to_mysql" /></div>
          <div><label className="text-sm font-medium text-gray-700">Descrição</label><input className={inp} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></div>
          <div><label className="text-sm font-medium text-gray-700">Grupo</label><input className={inp} value={form.group} onChange={(e) => setForm({ ...form, group: e.target.value })} placeholder="massa_teste" /></div>
          {editing && (
            <label className="flex items-center gap-2 text-sm text-gray-700"><input type="checkbox" className="h-4 w-4 rounded border-gray-300 text-brand-500" checked={form.active} onChange={(e) => setForm({ ...form, active: e.target.checked })} /> Ativo</label>
          )}
        </div>
      </Modal>

      {/* Excluir */}
      <Modal open={deleting != null} onClose={() => setDeleting(null)} title="Excluir pipeline"
        footer={<><SecondaryButton onClick={() => setDeleting(null)}>Cancelar</SecondaryButton>
          <PrimaryButton loading={del.isPending} onClick={() => deleting && del.mutate(deleting.id)} className="!bg-red-600 hover:!bg-red-700">Excluir</PrimaryButton></>}>
        {delError && <div className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{delError}</div>}
        <p className="text-sm text-gray-600">
          Tem certeza que deseja excluir o pipeline <b className="text-gray-900">{deleting?.name}</b>? Os steps, dependências e o histórico de execuções do pipeline serão removidos. Esta ação não pode ser desfeita.
        </p>
      </Modal>
    </div>
  );
}
