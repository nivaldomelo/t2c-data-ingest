import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Power, PowerOff, Tags as TagsIcon, Trash2 } from "lucide-react";

import { api } from "@/lib/api";
import type { Page } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { DataTable, EmptyState, PageHeader, PrimaryButton, SecondaryButton, StatusBadge } from "@/components/ui";
import type { Column } from "@/components/ui";
import { Modal } from "@/components/ui/Modal";
import { cn } from "@/lib/cn";
import type { Tag } from "@/features/tags/types";

export default function TagsPage() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const perms = { write: can("ingest:tags:write"), del: can("ingest:tags:delete") };
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Tag | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [deleting, setDeleting] = useState<Tag | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const { data, isLoading } = useQuery({ queryKey: ["tags"], queryFn: () => api.get<Page<Tag>>("/api/v1/tags?page=1&page_size=25") });
  const invalidate = () => qc.invalidateQueries({ queryKey: ["tags"] });

  const save = useMutation({
    mutationFn: () => editing ? api.put(`/api/v1/tags/${editing.id}`, { name, description: description || null }) : api.post("/api/v1/tags", { name, description: description || null }),
    onSuccess: () => { invalidate(); setOpen(false); },
    onError: (e) => setErr(e instanceof Error ? e.message : "Falha ao salvar"),
  });
  const toggle = useMutation({ mutationFn: (t: Tag) => api.post(`/api/v1/tags/${t.id}/${t.active ? "deactivate" : "activate"}`, {}), onSuccess: invalidate });
  const remove = useMutation({ mutationFn: (id: number) => api.del(`/api/v1/tags/${id}`), onSuccess: invalidate, onError: (e) => alert(e instanceof Error ? e.message : "Falha ao remover") });

  const columns: Column<Tag>[] = [
    { key: "name", header: "Nome", render: (t) => <span className="font-medium text-gray-900">{t.name}</span> },
    { key: "slug", header: "Slug", render: (t) => <span className="font-mono text-xs text-gray-500">{t.slug}</span> },
    { key: "desc", header: "Descrição", render: (t) => <span className="text-gray-600">{t.description ?? "—"}</span> },
    { key: "jobs", header: "Jobs", align: "center", render: (t) => t.jobs_count },
    { key: "active", header: "Ativa", render: (t) => <StatusBadge status={t.active ? "active" : "inactive"} /> },
    {
      key: "actions", header: "", align: "right",
      render: (t) => (
        <div className="flex items-center justify-end gap-0.5">
          {perms.write && (t.active
            ? <IconAction title="Inativar" onClick={() => toggle.mutate(t)}><PowerOff size={16} /></IconAction>
            : <IconAction title="Ativar" onClick={() => toggle.mutate(t)}><Power size={16} /></IconAction>)}
          {perms.write && <button onClick={() => { setEditing(t); setName(t.name); setDescription(t.description ?? ""); setErr(null); setOpen(true); }} className="rounded-lg px-2 py-1 text-xs text-gray-500 hover:bg-gray-100">Editar</button>}
          {perms.del && <IconAction title="Remover" danger onClick={() => setDeleting(t)}><Trash2 size={16} /></IconAction>}
        </div>
      ),
    },
  ];

  const inp = "mt-1.5 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-brand-400 focus:outline-none";

  return (
    <div>
      <PageHeader icon={<TagsIcon size={22} />} title="Tags" description="Gerencie as tags usadas para organizar e buscar jobs."
        actions={perms.write ? <PrimaryButton icon={<Plus size={16} />} onClick={() => { setEditing(null); setName(""); setDescription(""); setErr(null); setOpen(true); }}>Nova tag</PrimaryButton> : null} />
      <DataTable columns={columns} rows={data?.items ?? []} rowKey={(t) => t.id} loading={isLoading}
        empty={<EmptyState icon={<TagsIcon size={24} />} title="Nenhuma tag" description="Crie tags para organizar seus jobs." />} />

      <Modal open={open} onClose={() => setOpen(false)} title={editing ? "Editar tag" : "Nova tag"}
        footer={<><SecondaryButton onClick={() => setOpen(false)}>Cancelar</SecondaryButton><PrimaryButton loading={save.isPending} disabled={!name.trim()} onClick={() => save.mutate()}>Salvar</PrimaryButton></>}>
        {err && <div className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{err}</div>}
        <div className="space-y-3">
          <div><label className="text-sm font-medium text-gray-700">Nome *</label><input className={inp} value={name} onChange={(e) => setName(e.target.value)} placeholder="ex.: incremental" /></div>
          <div><label className="text-sm font-medium text-gray-700">Descrição</label><input className={inp} value={description} onChange={(e) => setDescription(e.target.value)} /></div>
          <p className="text-xs text-gray-400">O slug é gerado automaticamente a partir do nome (ex.: massa_teste → massa-teste).</p>
        </div>
      </Modal>

      <Modal open={!!deleting} onClose={() => setDeleting(null)} title="Remover tag"
        footer={<><SecondaryButton onClick={() => setDeleting(null)}>Cancelar</SecondaryButton><PrimaryButton className="bg-red-600 hover:bg-red-700" loading={remove.isPending} onClick={async () => { if (deleting) { await remove.mutateAsync(deleting.id); setDeleting(null); } }}>Remover</PrimaryButton></>}>
        <p className="text-sm text-gray-600">Remover a tag <span className="font-semibold text-gray-900">{deleting?.name}</span>? Só é possível se não estiver em uso.</p>
      </Modal>
    </div>
  );
}

function IconAction({ title, onClick, children, danger }: { title: string; onClick: () => void; children: React.ReactNode; danger?: boolean }) {
  return <button title={title} onClick={onClick} className={cn("inline-flex h-8 w-8 items-center justify-center rounded-lg text-gray-400 transition-colors", danger ? "hover:bg-red-50 hover:text-red-600" : "hover:bg-gray-100 hover:text-gray-700")}>{children}</button>;
}
