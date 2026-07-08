import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Database, Plus, Search, X } from "lucide-react";

import { api } from "@/lib/api";
import type { Page } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { PageHeader, PrimaryButton, SecondaryButton } from "@/components/ui";
import { Modal } from "@/components/ui/Modal";
import { IngestionControlSummaryCards } from "@/features/ingestion-control/IngestionControlSummaryCards";
import { IngestionControlTable } from "@/features/ingestion-control/IngestionControlTable";
import { IngestionControlForm } from "@/features/ingestion-control/IngestionControlForm";
import type { ControlPayload } from "@/features/ingestion-control/IngestionControlForm";
import { IngestionControlDetail } from "@/features/ingestion-control/IngestionControlDetail";
import type { IngestionControl, IngestionControlSummary } from "@/features/ingestion-control/types";
import {
  DESTINO_VALUES, ORIGEM_VALUES, STATUS_VALUES, TIPO_INGESTAO_VALUES, TIPO_TABELA_VALUES,
} from "@/features/ingestion-control/types";

const sel = "h-10 rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-700 focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-500/20";
const BASE = "/api/v1/ingestion-control";

export default function IngestionControlPage() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const perms = { write: can("ingest:control:write"), del: can("ingest:control:delete") };

  const [f, setF] = useState({ q: "", grupo: "", status: "", ativo: "", tipo_ingestao: "", tipo_tabela: "", origem: "", destino: "" });
  const [page, setPage] = useState(1);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<IngestionControl | null>(null);
  const [viewing, setViewing] = useState<IngestionControl | null>(null);
  const [deleting, setDeleting] = useState<IngestionControl | null>(null);

  const query = useMemo(() => {
    const p = new URLSearchParams({ page: String(page), page_size: "25" });
    if (f.q.trim()) p.set("q", f.q.trim());
    if (f.grupo) p.set("grupo", f.grupo);
    if (f.status) p.set("status", f.status);
    if (f.ativo) p.set("ativo", f.ativo);
    if (f.tipo_ingestao) p.set("tipo_ingestao", f.tipo_ingestao);
    if (f.tipo_tabela) p.set("tipo_tabela", f.tipo_tabela);
    if (f.origem) p.set("origem", f.origem);
    if (f.destino) p.set("destino", f.destino);
    return p.toString();
  }, [f, page]);

  const summary = useQuery({ queryKey: ["control-summary"], queryFn: () => api.get<IngestionControlSummary>(`${BASE}/summary`) });
  const list = useQuery({ queryKey: ["control", query], queryFn: () => api.get<Page<IngestionControl>>(`${BASE}?${query}`) });

  const invalidate = () => { qc.invalidateQueries({ queryKey: ["control"] }); qc.invalidateQueries({ queryKey: ["control-summary"] }); };
  const save = useMutation({
    mutationFn: (p: { payload: ControlPayload; id?: number }) => p.id ? api.put(`${BASE}/${p.id}`, p.payload) : api.post(BASE, p.payload),
    onSuccess: () => { invalidate(); setFormOpen(false); },
  });
  const toggle = useMutation({
    mutationFn: (r: IngestionControl) => api.post(`${BASE}/${r.id}/${r.ativo ? "deactivate" : "activate"}`, {}),
    onSuccess: invalidate,
  });
  const remove = useMutation({ mutationFn: (id: number) => api.del(`${BASE}/${id}`), onSuccess: invalidate });

  function upd(k: string, val: string) { setPage(1); setF((p) => ({ ...p, [k]: val })); }
  const opt = (vals: string[], all: string) => [<option key="" value="">{all}</option>, ...vals.map((x) => <option key={x} value={x}>{x}</option>)];
  const hasFilters = Object.values(f).some(Boolean);

  return (
    <div>
      <PageHeader
        icon={<Database size={22} />}
        title="Controle de Ingestão"
        description="Cadastre e gerencie os parâmetros das tabelas que serão processadas pelos jobs e pipelines."
        actions={perms.write ? <PrimaryButton icon={<Plus size={16} />} onClick={() => { setEditing(null); setFormOpen(true); }}>Novo controle</PrimaryButton> : null}
      />

      <IngestionControlSummaryCards summary={summary.data} loading={summary.isLoading} />

      <div className="mt-6 flex flex-wrap items-center gap-2">
        <div className="relative min-w-[200px] flex-1">
          <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input value={f.q} onChange={(e) => upd("q", e.target.value)} placeholder="Buscar por nome, grupo, origem, destino…" className="h-10 w-full rounded-lg border border-gray-200 bg-white pl-9 pr-3 text-sm text-gray-700 focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-500/20" />
        </div>
        <select className={sel} value={f.tipo_ingestao} onChange={(e) => upd("tipo_ingestao", e.target.value)}>{opt(TIPO_INGESTAO_VALUES, "Tipo ingestão")}</select>
        <select className={sel} value={f.tipo_tabela} onChange={(e) => upd("tipo_tabela", e.target.value)}>{opt(TIPO_TABELA_VALUES, "Tipo tabela")}</select>
        <select className={sel} value={f.origem} onChange={(e) => upd("origem", e.target.value)}>{opt(ORIGEM_VALUES, "Origem")}</select>
        <select className={sel} value={f.destino} onChange={(e) => upd("destino", e.target.value)}>{opt(DESTINO_VALUES, "Destino")}</select>
        <select className={sel} value={f.status} onChange={(e) => upd("status", e.target.value)}>{opt(STATUS_VALUES, "Status")}</select>
        <select className={sel} value={f.ativo} onChange={(e) => upd("ativo", e.target.value)}>
          <option value="">Ativos e inativos</option>
          <option value="true">Somente ativos</option>
          <option value="false">Somente inativos</option>
        </select>
        {hasFilters && (
          <button onClick={() => { setPage(1); setF({ q: "", grupo: "", status: "", ativo: "", tipo_ingestao: "", tipo_tabela: "", origem: "", destino: "" }); }} className="inline-flex items-center gap-1 rounded-lg px-3 py-2 text-sm text-gray-500 hover:text-gray-800">
            <X size={14} /> Limpar
          </button>
        )}
      </div>

      <div className="mt-4">
        <IngestionControlTable
          rows={list.data?.items ?? []}
          loading={list.isLoading}
          perms={perms}
          onView={setViewing}
          onEdit={(r) => { setEditing(r); setFormOpen(true); }}
          onToggle={(r) => toggle.mutate(r)}
          onDelete={setDeleting}
          pagination={list.data ? { page: list.data.page, totalPages: list.data.total_pages, total: list.data.total, hasMore: list.data.has_more, onPrev: () => setPage((p) => Math.max(1, p - 1)), onNext: () => setPage((p) => p + 1) } : undefined}
        />
      </div>

      <Modal open={formOpen} onClose={() => setFormOpen(false)} title={editing ? "Editar controle" : "Novo controle de ingestão"} description="Parâmetros usados pelos jobs e pipelines de ingestão." width="max-w-3xl">
        <IngestionControlForm
          initial={editing}
          canEditExecution={perms.write}
          saving={save.isPending}
          onSubmit={(payload) => save.mutate({ payload, id: editing?.id })}
          onCancel={() => setFormOpen(false)}
        />
      </Modal>

      <IngestionControlDetail item={viewing} onClose={() => setViewing(null)} />

      <Modal
        open={!!deleting}
        onClose={() => setDeleting(null)}
        title="Remover controle"
        footer={
          <>
            <SecondaryButton onClick={() => setDeleting(null)}>Cancelar</SecondaryButton>
            <PrimaryButton className="bg-red-600 hover:bg-red-700" loading={remove.isPending} onClick={async () => { if (deleting) { await remove.mutateAsync(deleting.id); setDeleting(null); } }}>Remover</PrimaryButton>
          </>
        }
      >
        <p className="text-sm text-gray-600">Remover o controle de <span className="font-semibold text-gray-900">{deleting?.nome_tabela}</span>? Esta ação não pode ser desfeita.</p>
      </Modal>
    </div>
  );
}
