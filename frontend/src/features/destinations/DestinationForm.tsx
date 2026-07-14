import { useMemo, useState } from "react";
import type { FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { Page } from "@/lib/api";
import { PrimaryButton, SecondaryButton } from "@/components/ui";
import type {
  Destination, DestinationSubmit, DestinationType,
} from "@/features/destinations/types";
import {
  COMPRESSIONS, FILE_FORMATS, PG_WRITE_MODES, S3_WRITE_MODES, UPSERT_STRATEGIES,
} from "@/features/destinations/types";

const label = "block text-sm font-medium text-gray-700";
const field =
  "mt-1.5 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-500/20";
const sectionTitle = "text-xs font-semibold uppercase tracking-wide text-gray-400";

interface ConnMin { id: number; name: string; connection_type: string }

export function DestinationForm({
  type, initial, saving, error, onSubmit, onCancel,
}: {
  type: DestinationType;
  initial: Destination | null;
  saving?: boolean;
  error?: string | null;
  onSubmit: (payload: DestinationSubmit) => void;
  onCancel: () => void;
}) {
  const isS3 = type === "s3";
  const [v, setV] = useState(() => ({
    name: initial?.name ?? "",
    description: initial?.description ?? "",
    connection_id: initial?.connection_id ?? 0,
    write_mode: initial?.write_mode ?? "append",
    is_template: initial?.is_template ?? false,
    active: initial?.active ?? true,
    // pg
    target_schema: initial?.target_schema ?? "",
    target_table: initial?.target_table ?? "",
    primary_key_columns: (initial?.primary_key_columns ?? []).join(","),
    staging_schema: initial?.staging_schema ?? "",
    staging_table: initial?.staging_table ?? "",
    upsert_strategy: initial?.upsert_strategy ?? "on_conflict",
    truncate_before_load: initial?.truncate_before_load ?? false,
    // s3
    target_bucket: initial?.target_bucket ?? "",
    target_layer: initial?.target_layer ?? "",
    target_prefix: initial?.target_prefix ?? "",
    file_format: initial?.file_format ?? "parquet",
    compression: initial?.compression ?? "snappy",
    partition_columns: (initial?.partition_columns ?? []).join(","),
  }));
  const [localErr, setLocalErr] = useState<string | null>(null);

  function set<K extends keyof typeof v>(k: K, val: (typeof v)[K]) {
    setV((p) => ({ ...p, [k]: val }));
  }

  // Conexões compatíveis com o tipo do destino.
  const conns = useQuery({
    queryKey: ["destination-conns", type],
    queryFn: () => api.get<Page<ConnMin>>(`/api/v1/connections?connection_type=${type}&page=1&page_size=200`),
  });
  const connItems = conns.data?.items ?? [];

  const isUpsert = !isS3 && v.write_mode === "upsert";
  const list = (s: string) => s.split(",").map((x) => x.trim()).filter(Boolean);

  function build(): DestinationSubmit | null {
    if (!v.name.trim()) { setLocalErr("Nome é obrigatório."); return null; }
    if (!v.connection_id) { setLocalErr("Selecione a conexão."); return null; }
    const base: DestinationSubmit = {
      name: v.name.trim(), description: v.description.trim() || null,
      destination_type: type, connection_id: Number(v.connection_id),
      write_mode: v.write_mode, is_template: v.is_template, active: v.active,
    };
    if (isS3) {
      if (!v.target_bucket.trim()) { setLocalErr("Bucket é obrigatório."); return null; }
      if (!v.target_layer.trim()) { setLocalErr("Camada é obrigatória."); return null; }
      if (!v.is_template && !v.target_prefix.trim()) { setLocalErr("Prefixo/path é obrigatório (ou marque como template)."); return null; }
      Object.assign(base, {
        target_bucket: v.target_bucket.trim(),
        target_layer: v.target_layer.trim(),
        target_prefix: v.target_prefix.trim().replace(/^\/+|\/+$/g, "") || null,
        file_format: v.file_format,
        compression: v.compression,
        partition_columns: list(v.partition_columns),
      });
    } else {
      if (!v.target_schema.trim()) { setLocalErr("Schema destino é obrigatório."); return null; }
      if (!v.is_template && !v.target_table.trim()) { setLocalErr("Tabela destino é obrigatória (ou marque como template)."); return null; }
      if (isUpsert && !list(v.primary_key_columns).length) { setLocalErr("Para upsert, informe as colunas chave."); return null; }
      if (isUpsert && !v.is_template && !v.staging_table.trim()) { setLocalErr("Para upsert, informe a tabela de staging (ou marque como template)."); return null; }
      Object.assign(base, {
        target_schema: v.target_schema.trim(),
        target_table: v.target_table.trim() || null,
        primary_key_columns: list(v.primary_key_columns),
        staging_schema: v.staging_schema.trim() || null,
        staging_table: v.staging_table.trim() || null,
        upsert_strategy: isUpsert ? v.upsert_strategy : null,
        truncate_before_load: v.truncate_before_load,
      });
    }
    return base;
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    setLocalErr(null);
    const p = build();
    if (p) onSubmit(p);
  }

  const writeModes = useMemo(() => (isS3 ? S3_WRITE_MODES : PG_WRITE_MODES), [isS3]);

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <label className={label}>Nome *</label>
          <input className={field} value={v.name} onChange={(e) => set("name", e.target.value)} placeholder={isS3 ? "ex.: Bronze Eventos Status" : "ex.: Postgres Spark Payments"} required />
        </div>
        <div className="sm:col-span-2">
          <label className={label}>Descrição</label>
          <input className={field} value={v.description} onChange={(e) => set("description", e.target.value)} />
        </div>
        <div className="sm:col-span-2">
          <label className={label}>Conexão {isS3 ? "S3" : "PostgreSQL"} *</label>
          <select className={field} value={v.connection_id} onChange={(e) => set("connection_id", Number(e.target.value))}>
            <option value={0}>Selecione…</option>
            {connItems.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          {connItems.length === 0 && !conns.isLoading && (
            <p className="mt-1 text-xs text-amber-600">Nenhuma conexão {isS3 ? "S3" : "PostgreSQL"} cadastrada.</p>
          )}
        </div>
      </div>

      {/* Template */}
      <div className="rounded-xl border border-gray-100 bg-gray-50/60 p-3">
        <label className="flex items-center gap-2 text-sm font-medium text-gray-700">
          <input type="checkbox" className="h-4 w-4 rounded border-gray-300 text-brand-500 focus:ring-brand-500/30" checked={v.is_template} onChange={(e) => set("is_template", e.target.checked)} />
          Destino template (reutilizável por várias tabelas)
        </label>
        <p className="mt-1 text-xs text-gray-500">
          {v.is_template
            ? (isS3
                ? "A tabela é anexada em runtime ao prefixo (vem do Controle de Ingestão ou de --table). Use {table} no prefixo para posição customizada. Ex.: bronze/{table}."
                : "A tabela vem em runtime (Controle de Ingestão nome_tabela ou --table). Deixe a tabela em branco ou use {table} na staging (ex.: stg_{table}). Um destino serve N tabelas.")
            : "Destino específico: aponta para uma única tabela/prefixo fixo."}
        </p>
      </div>

      {/* Alvo */}
      <div className="border-t border-gray-100 pt-3">
        <span className={sectionTitle}>{v.is_template ? "Alvo (raiz / padrão)" : "Alvo"}</span>
        <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-2">
          {isS3 ? (
            <>
              <div><label className={label}>Bucket *</label><input className={field} value={v.target_bucket} onChange={(e) => set("target_bucket", e.target.value)} /></div>
              <div><label className={label}>Camada *</label><input className={field} value={v.target_layer} onChange={(e) => set("target_layer", e.target.value)} placeholder="bronze / silver / gold" /></div>
              <div className="sm:col-span-2"><label className={label}>{v.is_template ? "Prefixo base" : "Prefixo / path *"}</label><input className={field} value={v.target_prefix} onChange={(e) => set("target_prefix", e.target.value)} placeholder={v.is_template ? "bronze  (a tabela é anexada em runtime) ou bronze/{table}" : "bronze/eventos_status"} /></div>
              <div><label className={label}>Formato *</label><select className={field} value={v.file_format} onChange={(e) => set("file_format", e.target.value)}>{FILE_FORMATS.map((f) => <option key={f} value={f}>{f}</option>)}</select></div>
              <div><label className={label}>Compressão</label><select className={field} value={v.compression} onChange={(e) => set("compression", e.target.value)}>{COMPRESSIONS.map((c) => <option key={c} value={c}>{c}</option>)}</select></div>
              <div className="sm:col-span-2"><label className={label}>Colunas de partição</label><input className={field} value={v.partition_columns} onChange={(e) => set("partition_columns", e.target.value)} placeholder="ano,mes,dia" /></div>
            </>
          ) : (
            <>
              <div><label className={label}>Schema destino *</label><input className={field} value={v.target_schema} onChange={(e) => set("target_schema", e.target.value)} placeholder="spark" /></div>
              <div><label className={label}>{v.is_template ? "Tabela (opcional — vem do runtime)" : "Tabela destino *"}</label><input className={field} value={v.target_table} onChange={(e) => set("target_table", e.target.value)} placeholder={v.is_template ? "{table}  (do Controle / --table)" : "payments"} /></div>
            </>
          )}
          <div><label className={label}>Modo de escrita *</label><select className={field} value={v.write_mode} onChange={(e) => set("write_mode", e.target.value)}>{writeModes.map((m) => <option key={m} value={m}>{m}</option>)}</select></div>
        </div>
      </div>

      {/* Upsert (Postgres) */}
      {isUpsert && (
        <div className="border-t border-gray-100 pt-3">
          <span className={sectionTitle}>Upsert</span>
          <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="sm:col-span-2"><label className={label}>Colunas chave *</label><input className={field} value={v.primary_key_columns} onChange={(e) => set("primary_key_columns", e.target.value)} placeholder="id  ou  id,order_id" /></div>
            <div><label className={label}>Schema staging</label><input className={field} value={v.staging_schema} onChange={(e) => set("staging_schema", e.target.value)} placeholder="(usa o schema destino)" /></div>
            <div><label className={label}>Tabela staging *</label><input className={field} value={v.staging_table} onChange={(e) => set("staging_table", e.target.value)} placeholder="stg_payments_ingest" /></div>
            <div><label className={label}>Estratégia</label><select className={field} value={v.upsert_strategy} onChange={(e) => set("upsert_strategy", e.target.value)}>{UPSERT_STRATEGIES.map((s) => <option key={s} value={s}>{s}</option>)}</select></div>
          </div>
        </div>
      )}

      <div className="flex flex-wrap gap-4 border-t border-gray-100 pt-3">
        {!isS3 && (
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input type="checkbox" className="h-4 w-4 rounded border-gray-300 text-brand-500 focus:ring-brand-500/30" checked={v.truncate_before_load} onChange={(e) => set("truncate_before_load", e.target.checked)} />
            Truncar antes de carregar
          </label>
        )}
        <label className="flex items-center gap-2 text-sm text-gray-700">
          <input type="checkbox" className="h-4 w-4 rounded border-gray-300 text-brand-500 focus:ring-brand-500/30" checked={v.active} onChange={(e) => set("active", e.target.checked)} />
          Ativo
        </label>
      </div>

      {(localErr || error) && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{localErr || error}</p>}

      <div className="flex items-center justify-end gap-2">
        <SecondaryButton type="button" onClick={onCancel}>Cancelar</SecondaryButton>
        <PrimaryButton type="submit" loading={saving}>Salvar</PrimaryButton>
      </div>
    </form>
  );
}
