import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Copy, Plus, Power, PowerOff, Search, Tags as TagsIcon, Trash2, X } from "lucide-react";

import { api } from "@/lib/api";
import type { Page } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Card, DataTable, EmptyState, PageHeader, PrimaryButton, SecondaryButton, StatusBadge } from "@/components/ui";
import type { Column } from "@/components/ui";
import { Modal } from "@/components/ui/Modal";
import { cn } from "@/lib/cn";
import type { Tag } from "@/features/tags/types";

const PAGE_SIZE = 12;

/** Curated swatches; value stored in Tag.color (hex). `null` = neutral/no color. */
const COLORS: { value: string | null; label: string }[] = [
  { value: null, label: "Neutra" },
  { value: "#ef4444", label: "Vermelho" },
  { value: "#f97316", label: "Laranja" },
  { value: "#f59e0b", label: "Âmbar" },
  { value: "#22c55e", label: "Verde" },
  { value: "#10b981", label: "Esmeralda" },
  { value: "#0ea5e9", label: "Céu" },
  { value: "#3b82f6", label: "Azul" },
  { value: "#6366f1", label: "Índigo" },
  { value: "#8b5cf6", label: "Violeta" },
  { value: "#ec4899", label: "Rosa" },
  { value: "#64748b", label: "Cinza" },
];

const STATUS_FILTERS = [
  { v: "all", l: "Ativas e inativas" },
  { v: "active", l: "Somente ativas" },
  { v: "inactive", l: "Somente inativas" },
] as const;

const SORTS = [
  { v: "name", l: "Nome A–Z" },
  { v: "jobs", l: "Mais usadas" },
  { v: "recent", l: "Mais recentes" },
] as const;

/** Mirror of backend slugify() for a live preview in the form. */
function slugify(name: string): string {
  return (name || "")
    .trim()
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
}

const selCls = "h-9 rounded-lg border border-gray-200 bg-white px-2.5 text-sm text-gray-700 outline-none focus:border-brand-500";

export default function TagsPage() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const perms = { write: can("ingest:tags:write"), del: can("ingest:tags:delete") };

  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Tag | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [color, setColor] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<Tag | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [delErr, setDelErr] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);

  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<(typeof STATUS_FILTERS)[number]["v"]>("all");
  const [sort, setSort] = useState<(typeof SORTS)[number]["v"]>("name");
  const [page, setPage] = useState(1);

  // Tag vocabularies are small; fetch all once and filter/sort/paginate client-side
  // for instant interaction and an accurate summary.
  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["tags"],
    queryFn: () => api.get<Page<Tag>>("/api/v1/tags?page=1&page_size=200"),
  });
  const invalidate = () => qc.invalidateQueries({ queryKey: ["tags"] });

  const all = data?.items ?? [];
  const summary = useMemo(() => ({
    total: all.length,
    active: all.filter((t) => t.active).length,
    inactive: all.filter((t) => !t.active).length,
    inUse: all.filter((t) => t.jobs_count > 0).length,
  }), [all]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    let rows = all.filter((t) => {
      if (status === "active" && !t.active) return false;
      if (status === "inactive" && t.active) return false;
      if (q && !t.name.toLowerCase().includes(q) && !t.slug.toLowerCase().includes(q) && !(t.description ?? "").toLowerCase().includes(q)) return false;
      return true;
    });
    rows = [...rows].sort((a, b) => {
      if (sort === "jobs") return b.jobs_count - a.jobs_count || a.name.localeCompare(b.name);
      if (sort === "recent") return (b.created_at ?? "").localeCompare(a.created_at ?? "");
      return a.name.localeCompare(b.name);
    });
    return rows;
  }, [all, search, status, sort]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const pageRows = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);
  const hasFilters = !!search.trim() || status !== "all";

  function resetForm() { setName(""); setDescription(""); setColor(null); setErr(null); }
  function openCreate() { setEditing(null); resetForm(); setOpen(true); }
  function openEdit(t: Tag) { setEditing(t); setName(t.name); setDescription(t.description ?? ""); setColor(t.color); setErr(null); setOpen(true); }
  function clearFilters() { setSearch(""); setStatus("all"); setPage(1); }

  async function copySlug(slug: string) {
    try { await navigator.clipboard.writeText(slug); setCopied(slug); setTimeout(() => setCopied((c) => (c === slug ? null : c)), 1200); } catch { /* ignore */ }
  }

  const save = useMutation({
    mutationFn: () => {
      const body = { name: name.trim(), description: description.trim() || null, color };
      return editing ? api.put(`/api/v1/tags/${editing.id}`, body) : api.post("/api/v1/tags", body);
    },
    onSuccess: () => { invalidate(); setOpen(false); },
    onError: (e) => setErr(e instanceof Error ? e.message : "Falha ao salvar"),
  });
  const toggle = useMutation({ mutationFn: (t: Tag) => api.post(`/api/v1/tags/${t.id}/${t.active ? "deactivate" : "activate"}`, {}), onSuccess: invalidate });
  const remove = useMutation({
    mutationFn: (id: number) => api.del(`/api/v1/tags/${id}`),
    onSuccess: () => { invalidate(); setDeleting(null); },
    onError: (e) => setDelErr(e instanceof Error ? e.message : "Falha ao remover"),
  });

  const previewSlug = slugify(name);
  const slugChanged = editing && previewSlug && previewSlug !== editing.slug;

  const columns: Column<Tag>[] = [
    {
      key: "name", header: "Nome",
      render: (t) => (
        <span className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 shrink-0 rounded-full ring-1 ring-inset ring-black/5" style={{ background: t.color ?? "#d1d5db" }} />
          <span className="font-medium text-gray-900">{t.name}</span>
        </span>
      ),
    },
    {
      key: "slug", header: "Slug",
      render: (t) => (
        <button onClick={() => copySlug(t.slug)} title="Copiar slug"
          className="group inline-flex items-center gap-1.5 rounded-md px-1.5 py-0.5 font-mono text-xs text-gray-500 hover:bg-gray-100">
          {t.slug}
          {copied === t.slug
            ? <Check size={12} className="text-emerald-500" />
            : <Copy size={12} className="text-gray-300 group-hover:text-gray-500" />}
        </button>
      ),
    },
    { key: "desc", header: "Descrição", render: (t) => <span className="text-gray-600">{t.description ?? "—"}</span> },
    {
      key: "jobs", header: "Jobs", align: "center",
      render: (t) => (
        <span className={cn("inline-flex min-w-[1.75rem] justify-center rounded-full px-2 py-0.5 text-xs font-medium",
          t.jobs_count > 0 ? "bg-brand-50 text-brand-700" : "bg-gray-100 text-gray-400")}>
          {t.jobs_count}
        </span>
      ),
    },
    { key: "active", header: "Ativa", render: (t) => <StatusBadge status={t.active ? "active" : "inactive"} /> },
    {
      key: "actions", header: "", align: "right",
      render: (t) => (
        <div className="flex items-center justify-end gap-0.5">
          {perms.write && (t.active
            ? <IconAction title="Inativar" onClick={() => toggle.mutate(t)}><PowerOff size={16} /></IconAction>
            : <IconAction title="Ativar" onClick={() => toggle.mutate(t)}><Power size={16} /></IconAction>)}
          {perms.write && <button onClick={() => openEdit(t)} className="rounded-lg px-2 py-1 text-xs text-gray-500 hover:bg-gray-100">Editar</button>}
          {perms.del && (
            <IconAction title={t.jobs_count > 0 ? "Em uso — remova os vínculos antes" : "Remover"} danger disabled={t.jobs_count > 0}
              onClick={() => { setDelErr(null); setDeleting(t); }}><Trash2 size={16} /></IconAction>
          )}
        </div>
      ),
    },
  ];

  const inp = "mt-1.5 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-brand-400 focus:outline-none";

  return (
    <div>
      <PageHeader icon={<TagsIcon size={22} />} title="Tags" description="Gerencie as tags usadas para organizar e buscar jobs."
        actions={perms.write ? <PrimaryButton icon={<Plus size={16} />} onClick={openCreate}>Nova tag</PrimaryButton> : null} />

      {/* summary */}
      <div className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-4">
        <SummaryCard label="Total de tags" value={summary.total} />
        <SummaryCard label="Ativas" value={summary.active} accent="emerald" />
        <SummaryCard label="Inativas" value={summary.inactive} />
        <SummaryCard label="Em uso" value={summary.inUse} accent="brand" />
      </div>

      {/* filters */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="relative min-w-[220px] flex-1 max-w-sm">
          <Search size={15} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" />
          <input value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} placeholder="Buscar por nome, slug ou descrição…"
            className="h-9 w-full rounded-lg border border-gray-200 bg-white pl-8 pr-3 text-sm outline-none focus:border-brand-500" />
        </div>
        <select className={selCls} value={status} onChange={(e) => { setStatus(e.target.value as typeof status); setPage(1); }}>
          {STATUS_FILTERS.map((o) => <option key={o.v} value={o.v}>{o.l}</option>)}
        </select>
        <select className={selCls} value={sort} onChange={(e) => { setSort(e.target.value as typeof sort); setPage(1); }}>
          {SORTS.map((o) => <option key={o.v} value={o.v}>{o.l}</option>)}
        </select>
        {hasFilters && <button onClick={clearFilters} className="inline-flex h-9 items-center gap-1 rounded-lg px-2.5 text-sm text-gray-500 hover:bg-gray-100"><X size={14} /> Limpar</button>}
        <span className="ml-auto text-sm text-gray-400">
          {filtered.length > 0 ? `${filtered.length} tag(s)` : ""}{isFetching && " · atualizando…"}
        </span>
      </div>

      <DataTable columns={columns} rows={pageRows} rowKey={(t) => t.id} loading={isLoading}
        pagination={{
          page: safePage, totalPages, total: filtered.length,
          hasMore: safePage < totalPages,
          onPrev: () => setPage((p) => Math.max(1, p - 1)),
          onNext: () => setPage((p) => Math.min(totalPages, p + 1)),
        }}
        empty={hasFilters
          ? <EmptyState icon={<Search size={24} />} title="Nenhuma tag encontrada" description="Nenhuma tag corresponde aos filtros atuais."
              action={<SecondaryButton onClick={clearFilters}>Limpar filtros</SecondaryButton>} />
          : <EmptyState icon={<TagsIcon size={24} />} title="Nenhuma tag" description="Crie tags para organizar seus jobs."
              action={perms.write ? <PrimaryButton icon={<Plus size={16} />} onClick={openCreate}>Nova tag</PrimaryButton> : undefined} />} />

      <Modal open={open} onClose={() => setOpen(false)} title={editing ? "Editar tag" : "Nova tag"}
        footer={<><SecondaryButton onClick={() => setOpen(false)}>Cancelar</SecondaryButton><PrimaryButton loading={save.isPending} disabled={!name.trim()} onClick={() => save.mutate()}>Salvar</PrimaryButton></>}>
        {err && <div className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{err}</div>}
        <div className="space-y-4">
          <div>
            <label className="text-sm font-medium text-gray-700">Nome *</label>
            <input className={inp} value={name} onChange={(e) => setName(e.target.value)} placeholder="ex.: incremental" autoFocus />
            {name.trim() && (
              <p className="mt-1.5 text-xs text-gray-400">
                Slug: <span className="font-mono text-gray-500">{previewSlug || "—"}</span>
                {slugChanged && <span className="ml-1 text-amber-600">· o slug será alterado</span>}
              </p>
            )}
          </div>
          <div>
            <label className="text-sm font-medium text-gray-700">Descrição</label>
            <textarea className={cn(inp, "resize-none")} rows={2} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Opcional — para que serve esta tag." />
          </div>
          <div>
            <label className="text-sm font-medium text-gray-700">Cor</label>
            <div className="mt-2 flex flex-wrap gap-2">
              {COLORS.map((c) => {
                const selected = color === c.value;
                return (
                  <button key={c.label} type="button" title={c.label} onClick={() => setColor(c.value)}
                    className={cn("flex h-7 w-7 items-center justify-center rounded-full ring-1 ring-inset ring-black/5 transition-transform hover:scale-110",
                      selected && "ring-2 ring-offset-2 ring-brand-500")}
                    style={{ background: c.value ?? "#e5e7eb" }}>
                    {selected && <Check size={14} className={c.value ? "text-white" : "text-gray-600"} />}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </Modal>

      <Modal open={!!deleting} onClose={() => setDeleting(null)} title="Remover tag"
        footer={<><SecondaryButton onClick={() => setDeleting(null)}>Cancelar</SecondaryButton><PrimaryButton className="bg-red-600 hover:bg-red-700" loading={remove.isPending} disabled={(deleting?.jobs_count ?? 0) > 0} onClick={() => deleting && remove.mutate(deleting.id)}>Remover</PrimaryButton></>}>
        {delErr && <div className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{delErr}</div>}
        {(deleting?.jobs_count ?? 0) > 0
          ? <p className="text-sm text-gray-600">A tag <span className="font-semibold text-gray-900">{deleting?.name}</span> está em uso por <span className="font-semibold">{deleting?.jobs_count}</span> job(s). Remova os vínculos antes de excluir.</p>
          : <p className="text-sm text-gray-600">Remover a tag <span className="font-semibold text-gray-900">{deleting?.name}</span>? Esta ação não pode ser desfeita.</p>}
      </Modal>
    </div>
  );
}

function SummaryCard({ label, value, accent }: { label: string; value: number | undefined; accent?: "brand" | "emerald" }) {
  const tone = accent === "brand" ? "text-brand-600" : accent === "emerald" ? "text-emerald-600" : "text-gray-900";
  return (
    <Card className="p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-gray-400">{label}</p>
      <p className={cn("mt-1.5 text-2xl font-bold", tone)}>{value ?? "—"}</p>
    </Card>
  );
}

function IconAction({ title, onClick, children, danger, disabled }: { title: string; onClick: () => void; children: React.ReactNode; danger?: boolean; disabled?: boolean }) {
  return (
    <button title={title} onClick={onClick} disabled={disabled}
      className={cn("inline-flex h-8 w-8 items-center justify-center rounded-lg text-gray-400 transition-colors",
        disabled ? "cursor-not-allowed opacity-30" : danger ? "hover:bg-red-50 hover:text-red-600" : "hover:bg-gray-100 hover:text-gray-700")}>
      {children}
    </button>
  );
}
