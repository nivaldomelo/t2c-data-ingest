import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Trash2, X } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import type { Page } from "@/lib/api";
import { PrimaryButton, SecondaryButton } from "@/components/ui";
import { cn } from "@/lib/cn";

/** Destino genérico (brief) embutido no vínculo, para compor o alvo efetivo. */
interface DestBrief {
  id: number; name: string; destination_type: string;
  target_layer: string | null; target_schema: string | null; target_table: string | null;
  target_database: string | null; staging_schema: string | null;
  target_bucket: string | null; target_prefix: string | null; target_path: string | null;
  file_format: string | null; compression: string | null; write_mode: string | null;
  partition_columns: string[] | null;
}

interface ControlDestination {
  id: number; control_id: number; destination_id: number;
  destination_role: string; write_order: number; required: boolean; stop_on_failure: boolean; active: boolean;
  // overrides
  target_schema: string | null; target_table: string | null; target_relative_path: string | null;
  write_mode: string | null; file_format: string | null; compression: string | null;
  partition_columns: string[] | null; primary_key_columns: string[] | null; staging_table: string | null;
  destination: DestBrief | null;
}

interface DestOption { id: number; name: string; destination_type: string; target_display: string | null }

const ROLES = [
  { v: "primary", l: "Destino principal" },
  { v: "datalake_copy", l: "Cópia Data Lake" },
  { v: "audit_copy", l: "Cópia de auditoria" },
];
const ROLE_LABEL: Record<string, string> = Object.fromEntries(ROLES.map((r) => [r.v, r.l]));

const field = "mt-1 w-full rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-sm text-gray-900 focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-500/20";
const lbl = "block text-xs font-medium text-gray-600";

function join(bucket: string | null, prefix: string | null, rel: string | null): string {
  if (!bucket) return "—";
  const parts = [(prefix ?? "").replace(/^\/+|\/+$/g, ""), (rel ?? "").replace(/^\/+|\/+$/g, "")].filter(Boolean);
  const tail = parts.join("/");
  return `s3a://${bucket}/${tail ? tail + "/" : ""}`;
}

/** Alvo EFETIVO da carga = override do vínculo → base do destino → nome da carga. */
function effectiveTarget(l: ControlDestination, controlTable: string): string {
  const d = l.destination;
  if (!d) return "—";
  const tbl = l.target_table || d.target_table || controlTable;
  if (d.destination_type === "s3") {
    const rel = l.target_relative_path || tbl;
    const path = d.target_path && !l.target_relative_path ? d.target_path : join(d.target_bucket, d.target_prefix, rel);
    const parts = (l.partition_columns ?? d.partition_columns ?? []).join("/");
    const fmt = l.file_format || d.file_format || "parquet";
    return [path, fmt, parts].filter(Boolean).join(" · ");
  }
  const schema = l.target_schema || d.target_schema || "";
  const wm = l.write_mode || d.write_mode || "append";
  return [`${schema}.${tbl}`.replace(/^\./, ""), wm].filter(Boolean).join(" · ");
}

export function ControlDestinationsManager({ controlId, controlTable, canWrite }: { controlId: number; controlTable: string; canWrite: boolean }) {
  const qc = useQueryClient();
  const key = ["control-destinations", controlId];
  const { data } = useQuery({ queryKey: key, queryFn: () => api.get<ControlDestination[]>(`/api/v1/ingestion-control/${controlId}/destinations`) });
  const destinations = useQuery({
    queryKey: ["destinations-min"],
    queryFn: () => api.get<Page<DestOption>>("/api/v1/destinations?page=1&page_size=200&active=true"),
  });
  const links = data ?? [];
  const destItems = destinations.data?.items ?? [];
  const invalidate = () => qc.invalidateQueries({ queryKey: key });

  const [editing, setEditing] = useState<ControlDestination | "new" | null>(null);
  const remove = useMutation({
    mutationFn: (linkId: number) => api.del(`/api/v1/ingestion-control/${controlId}/destinations/${linkId}`),
    onSuccess: invalidate,
    onError: (e) => alert(e instanceof ApiError ? e.message : "Falha ao remover vínculo"),
  });

  return (
    <div className="col-span-2 space-y-2">
      {links.length === 0 && <p className="text-sm text-gray-400">Nenhum destino vinculado a esta carga.</p>}
      {links.map((l) => (
        <div key={l.id} className="flex items-start gap-3 rounded-lg border border-gray-100 bg-gray-50/60 px-3 py-2">
          <span className="mt-0.5 shrink-0 rounded bg-brand-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-brand-700">
            {l.write_order}. {ROLE_LABEL[l.destination_role] ?? l.destination_role}
          </span>
          <div className="min-w-0 flex-1">
            <div className="text-sm font-medium text-gray-800">{l.destination?.name ?? "—"} <span className="text-gray-400">· {l.destination?.destination_type}</span>{!l.active && <span className="ml-1 text-gray-400">(inativo)</span>}</div>
            <div className="truncate font-mono text-xs text-gray-500">{effectiveTarget(l, controlTable)}</div>
          </div>
          {canWrite && (
            <div className="flex shrink-0 gap-0.5">
              <button title="Editar" onClick={() => setEditing(l)} className="inline-flex h-7 w-7 items-center justify-center rounded-lg text-gray-400 hover:bg-gray-100 hover:text-gray-700"><Pencil size={14} /></button>
              <button title="Remover" onClick={() => { if (confirm(`Remover vínculo com ${l.destination?.name}?`)) remove.mutate(l.id); }} className="inline-flex h-7 w-7 items-center justify-center rounded-lg text-gray-400 hover:bg-red-50 hover:text-red-600"><Trash2 size={14} /></button>
            </div>
          )}
        </div>
      ))}
      {canWrite && editing == null && (
        <button onClick={() => setEditing("new")} className="inline-flex items-center gap-1.5 rounded-lg border border-dashed border-gray-300 px-3 py-1.5 text-sm text-gray-500 hover:border-brand-300 hover:text-brand-600">
          <Plus size={14} /> Vincular destino
        </button>
      )}
      {editing != null && (
        <LinkEditor
          controlId={controlId} controlTable={controlTable} destItems={destItems}
          link={editing === "new" ? null : editing}
          onDone={() => { setEditing(null); invalidate(); }}
          onCancel={() => setEditing(null)}
        />
      )}
    </div>
  );
}

function LinkEditor({ controlId, destItems, link, onDone, onCancel }: {
  controlId: number; controlTable: string; destItems: DestOption[];
  link: ControlDestination | null; onDone: () => void; onCancel: () => void;
}) {
  const isNew = link == null;
  const [v, setV] = useState({
    destination_id: link?.destination_id ? String(link.destination_id) : "",
    destination_role: link?.destination_role ?? "primary",
    write_order: String(link?.write_order ?? 1),
    target_schema: link?.target_schema ?? "",
    target_table: link?.target_table ?? "",
    target_relative_path: link?.target_relative_path ?? "",
    write_mode: link?.write_mode ?? "",
    file_format: link?.file_format ?? "",
    compression: link?.compression ?? "",
    partition_columns: (link?.partition_columns ?? []).join(","),
    primary_key_columns: (link?.primary_key_columns ?? []).join(","),
    staging_table: link?.staging_table ?? "",
  });
  const [err, setErr] = useState<string | null>(null);
  function set<K extends keyof typeof v>(k: K, val: (typeof v)[K]) { setV((p) => ({ ...p, [k]: val })); }
  const selDest = destItems.find((d) => String(d.id) === v.destination_id);
  const isS3 = selDest?.destination_type === "s3";
  const list = (s: string) => { const a = s.split(",").map((x) => x.trim()).filter(Boolean); return a.length ? a : null; };
  const str = (s: string) => (s.trim() === "" ? null : s.trim());

  const save = useMutation({
    mutationFn: () => {
      const body: Record<string, unknown> = {
        destination_role: v.destination_role,
        write_order: Number(v.write_order) || 1,
        target_schema: str(v.target_schema),
        target_table: str(v.target_table),
        target_relative_path: str(v.target_relative_path),
        write_mode: str(v.write_mode),
        file_format: str(v.file_format),
        compression: str(v.compression),
        partition_columns: list(v.partition_columns),
        primary_key_columns: list(v.primary_key_columns),
        staging_table: str(v.staging_table),
      };
      if (isNew) {
        if (!v.destination_id) throw new Error("Selecione um destino.");
        return api.post(`/api/v1/ingestion-control/${controlId}/destinations`, { destination_id: Number(v.destination_id), ...body });
      }
      return api.patch(`/api/v1/ingestion-control/${controlId}/destinations/${link!.id}`, body);
    },
    onSuccess: onDone,
    onError: (e) => setErr(e instanceof ApiError ? e.message : e instanceof Error ? e.message : "Falha ao salvar"),
  });

  return (
    <div className="rounded-xl border border-brand-200 bg-brand-50/30 p-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wide text-brand-700">{isNew ? "Novo vínculo" : "Editar vínculo"}</span>
        <button onClick={onCancel} className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-700"><X size={14} /></button>
      </div>
      <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
        <div>
          <label className={lbl}>Destino *</label>
          <select className={field} value={v.destination_id} disabled={!isNew} onChange={(e) => set("destination_id", e.target.value)}>
            <option value="">Selecione…</option>
            {destItems.map((d) => <option key={d.id} value={String(d.id)}>{d.name} · {d.destination_type}</option>)}
          </select>
        </div>
        <div>
          <label className={lbl}>Papel</label>
          <select className={field} value={v.destination_role} onChange={(e) => set("destination_role", e.target.value)}>
            {ROLES.map((r) => <option key={r.v} value={r.v}>{r.l}</option>)}
          </select>
        </div>
        {isS3 ? (
          <>
            <div><label className={lbl}>Path relativo</label><input className={field} value={v.target_relative_path} onChange={(e) => set("target_relative_path", e.target.value)} placeholder="clientes  (vazio = nome da carga)" /></div>
            <div><label className={lbl}>Partições</label><input className={field} value={v.partition_columns} onChange={(e) => set("partition_columns", e.target.value)} placeholder="ano,mes,dia" /></div>
            <div><label className={lbl}>Formato</label><input className={field} value={v.file_format} onChange={(e) => set("file_format", e.target.value)} placeholder="(padrão do destino)" /></div>
            <div><label className={lbl}>Write mode</label><input className={field} value={v.write_mode} onChange={(e) => set("write_mode", e.target.value)} placeholder="(padrão do destino)" /></div>
          </>
        ) : (
          <>
            <div><label className={lbl}>Schema destino</label><input className={field} value={v.target_schema} onChange={(e) => set("target_schema", e.target.value)} placeholder="(padrão do destino)" /></div>
            <div><label className={lbl}>Tabela destino</label><input className={field} value={v.target_table} onChange={(e) => set("target_table", e.target.value)} placeholder="clientes  (vazio = nome da carga)" /></div>
            <div><label className={lbl}>Chaves (upsert)</label><input className={field} value={v.primary_key_columns} onChange={(e) => set("primary_key_columns", e.target.value)} placeholder="cliente_uuid" /></div>
            <div><label className={lbl}>Staging table</label><input className={field} value={v.staging_table} onChange={(e) => set("staging_table", e.target.value)} placeholder="stg_clientes_ingest" /></div>
            <div><label className={lbl}>Write mode</label><input className={field} value={v.write_mode} onChange={(e) => set("write_mode", e.target.value)} placeholder="(padrão do destino)" /></div>
          </>
        )}
        <div><label className={lbl}>Ordem de escrita</label><input type="number" min={1} className={field} value={v.write_order} onChange={(e) => set("write_order", e.target.value)} /></div>
      </div>
      {err && <p className={cn("mt-2 rounded-lg bg-red-50 px-2.5 py-1.5 text-xs text-red-700")}>{err}</p>}
      <div className="mt-3 flex justify-end gap-2">
        <SecondaryButton size="sm" type="button" onClick={onCancel}>Cancelar</SecondaryButton>
        <PrimaryButton size="sm" loading={save.isPending} onClick={() => { setErr(null); save.mutate(); }}>Salvar</PrimaryButton>
      </div>
    </div>
  );
}
