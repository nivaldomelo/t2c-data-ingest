import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Search, Variable as VarIcon, X } from "lucide-react";

import { api } from "@/lib/api";
import type { Page } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { PageHeader, PrimaryButton, SecondaryButton } from "@/components/ui";
import { Modal } from "@/components/ui/Modal";
import { VariableSummaryCards } from "@/features/variables/VariableSummaryCards";
import { VariableTable } from "@/features/variables/VariableTable";
import { VariableForm } from "@/features/variables/VariableForm";
import type { VariablePayload } from "@/features/variables/VariableForm";
import { VariableDetail } from "@/features/variables/VariableDetail";
import type { Variable, VariableSummary } from "@/features/variables/types";
import { ENVIRONMENTS, VARIABLE_SCOPES, VARIABLE_TYPES } from "@/features/variables/types";

const sel = "h-10 rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-700 focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-500/20";
const BASE = "/api/v1/variables";

export default function VariablesPage() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const perms = { write: can("ingest:variables:write"), del: can("ingest:variables:delete") };

  const [f, setF] = useState({ search: "", variable_type: "", scope: "", environment: "", active: "", is_secret: "" });
  const [page, setPage] = useState(1);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Variable | null>(null);
  const [viewing, setViewing] = useState<Variable | null>(null);
  const [deleting, setDeleting] = useState<Variable | null>(null);

  const query = useMemo(() => {
    const p = new URLSearchParams({ page: String(page), page_size: "25" });
    Object.entries(f).forEach(([k, v]) => { if (v) p.set(k, v); });
    return p.toString();
  }, [f, page]);

  const summary = useQuery({ queryKey: ["variables-summary"], queryFn: () => api.get<VariableSummary>(`${BASE}/summary`) });
  const list = useQuery({ queryKey: ["variables", query], queryFn: () => api.get<Page<Variable>>(`${BASE}?${query}`) });

  const invalidate = () => { qc.invalidateQueries({ queryKey: ["variables"] }); qc.invalidateQueries({ queryKey: ["variables-summary"] }); };
  const save = useMutation({
    mutationFn: (p: { payload: VariablePayload; id?: number }) => p.id ? api.put(`${BASE}/${p.id}`, p.payload) : api.post(BASE, p.payload),
    onSuccess: () => { invalidate(); setFormOpen(false); },
  });
  const toggle = useMutation({ mutationFn: (v: Variable) => api.post(`${BASE}/${v.id}/${v.active ? "deactivate" : "activate"}`, {}), onSuccess: invalidate });
  const remove = useMutation({ mutationFn: (id: number) => api.del(`${BASE}/${id}`), onSuccess: invalidate });

  function upd(k: string, v: string) { setPage(1); setF((p) => ({ ...p, [k]: v })); }
  const opt = (vals: string[], all: string) => [<option key="" value="">{all}</option>, ...vals.map((x) => <option key={x} value={x}>{x}</option>)];
  const [saveError, setSaveError] = useState<string | null>(null);

  async function handleSubmit(payload: VariablePayload) {
    setSaveError(null);
    try {
      await save.mutateAsync({ payload, id: editing?.id });
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Falha ao salvar");
    }
  }

  const hasFilters = Object.values(f).some(Boolean);

  return (
    <div>
      <PageHeader
        icon={<VarIcon size={22} />}
        title="Variáveis"
        description="Gerencie variáveis reutilizáveis para parametrizar jobs, pipelines e execuções."
        actions={perms.write ? <PrimaryButton icon={<Plus size={16} />} onClick={() => { setEditing(null); setSaveError(null); setFormOpen(true); }}>Nova variável</PrimaryButton> : null}
      />

      <VariableSummaryCards summary={summary.data} loading={summary.isLoading} />

      <div className="mt-6 flex flex-wrap items-center gap-2">
        <div className="relative min-w-[200px] flex-1">
          <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input value={f.search} onChange={(e) => upd("search", e.target.value)} placeholder="Buscar por nome ou descrição…" className="h-10 w-full rounded-lg border border-gray-200 bg-white pl-9 pr-3 text-sm text-gray-700 focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-500/20" />
        </div>
        <select className={sel} value={f.variable_type} onChange={(e) => upd("variable_type", e.target.value)}>{opt(VARIABLE_TYPES, "Tipo")}</select>
        <select className={sel} value={f.scope} onChange={(e) => upd("scope", e.target.value)}>{opt(VARIABLE_SCOPES, "Escopo")}</select>
        <select className={sel} value={f.environment} onChange={(e) => upd("environment", e.target.value)}>{opt(ENVIRONMENTS, "Ambiente")}</select>
        <select className={sel} value={f.active} onChange={(e) => upd("active", e.target.value)}>
          <option value="">Ativas e inativas</option><option value="true">Ativas</option><option value="false">Inativas</option>
        </select>
        <select className={sel} value={f.is_secret} onChange={(e) => upd("is_secret", e.target.value)}>
          <option value="">Todas</option><option value="true">Secretas</option><option value="false">Não secretas</option>
        </select>
        {hasFilters && (
          <button onClick={() => { setPage(1); setF({ search: "", variable_type: "", scope: "", environment: "", active: "", is_secret: "" }); }} className="inline-flex items-center gap-1 rounded-lg px-3 py-2 text-sm text-gray-500 hover:text-gray-800">
            <X size={14} /> Limpar
          </button>
        )}
      </div>

      <div className="mt-4">
        <VariableTable
          rows={list.data?.items ?? []}
          loading={list.isLoading}
          perms={perms}
          onView={setViewing}
          onEdit={(v) => { setEditing(v); setSaveError(null); setFormOpen(true); }}
          onToggle={(v) => toggle.mutate(v)}
          onDelete={setDeleting}
          pagination={list.data ? { page: list.data.page, totalPages: list.data.total_pages, total: list.data.total, hasMore: list.data.has_more, onPrev: () => setPage((p) => Math.max(1, p - 1)), onNext: () => setPage((p) => p + 1) } : undefined}
        />
      </div>

      <Modal open={formOpen} onClose={() => setFormOpen(false)} title={editing ? "Editar variável" : "Nova variável"} description="Parâmetro reutilizável injetado como variável de ambiente na execução." width="max-w-2xl">
        {saveError && <div className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{saveError}</div>}
        <VariableForm initial={editing} saving={save.isPending} onSubmit={handleSubmit} onCancel={() => setFormOpen(false)} />
      </Modal>

      <VariableDetail item={viewing} onClose={() => setViewing(null)} />

      <Modal open={!!deleting} onClose={() => setDeleting(null)} title="Remover variável"
        footer={<>
          <SecondaryButton onClick={() => setDeleting(null)}>Cancelar</SecondaryButton>
          <PrimaryButton className="bg-red-600 hover:bg-red-700" loading={remove.isPending} onClick={async () => { if (deleting) { await remove.mutateAsync(deleting.id); setDeleting(null); } }}>Remover</PrimaryButton>
        </>}>
        <p className="text-sm text-gray-600">Remover a variável <span className="font-mono font-semibold text-gray-900">{deleting?.name}</span>?</p>
      </Modal>
    </div>
  );
}
