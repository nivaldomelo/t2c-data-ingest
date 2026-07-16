import { useMemo, useState } from "react";
import type { FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { Page } from "@/lib/api";
import { PrimaryButton, SecondaryButton, HelpBanner } from "@/components/ui";
import type {
  Destination, DestinationSubmit, DestinationType,
} from "@/features/destinations/types";
import {
  COMPRESSIONS, FILE_FORMATS, PG_WRITE_MODES, S3_WRITE_MODES,
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
    active: initial?.active ?? true,
    // pg (base)
    target_database: initial?.target_database ?? "",
    target_schema: initial?.target_schema ?? "",
    staging_schema: initial?.staging_schema ?? "",
    // s3 (base)
    target_bucket: initial?.target_bucket ?? "",
    target_layer: initial?.target_layer ?? "",
    target_prefix: initial?.target_prefix ?? "",
    file_format: initial?.file_format ?? "parquet",
    compression: initial?.compression ?? "snappy",
    encryption_mode: initial?.encryption_mode ?? "SSE-S3",
    kms_key_id: initial?.kms_key_id ?? "",
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

  function build(): DestinationSubmit | null {
    if (!v.name.trim()) { setLocalErr("Nome é obrigatório."); return null; }
    if (!v.connection_id) { setLocalErr("Selecione a conexão."); return null; }
    const base: DestinationSubmit = {
      name: v.name.trim(), description: v.description.trim() || null,
      destination_type: type, connection_id: Number(v.connection_id),
      write_mode: v.write_mode, active: v.active,
    };
    if (isS3) {
      if (!v.target_bucket.trim()) { setLocalErr("Bucket é obrigatório."); return null; }
      if (!v.target_layer.trim()) { setLocalErr("Camada é obrigatória."); return null; }
      Object.assign(base, {
        target_bucket: v.target_bucket.trim(),
        target_layer: v.target_layer.trim(),
        target_prefix: v.target_prefix.trim().replace(/^\/+|\/+$/g, "") || null,
        file_format: v.file_format,
        compression: v.compression,
        encryption_mode: v.encryption_mode || null,
        kms_key_id: v.encryption_mode === "SSE-KMS" ? (v.kms_key_id.trim() || null) : null,
      });
    } else {
      if (!v.target_schema.trim()) { setLocalErr("Schema padrão é obrigatório."); return null; }
      Object.assign(base, {
        target_database: v.target_database.trim() || null,
        target_schema: v.target_schema.trim(),
        staging_schema: v.staging_schema.trim() || null,
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
      <HelpBanner title="O que é um Destino?">
        Um destino é um <b>alvo técnico reutilizável</b> — <b>onde</b> gravar, sem credenciais (elas ficam
        na conexão). PostgreSQL: banco + schema padrão. S3/Data Lake: bucket + prefixo base + camada
        (bronze/silver/gold) + formato. <b>Não</b> é por tabela: a tabela, o path relativo, as partições e as
        chaves de cada carga ficam no <b>Controle de Ingestão</b>. Assim, poucos destinos servem N tabelas
        (ex.: um "PostgreSQL Massa Teste" e um "Data Lake Bronze" atendem todas as cargas do grupo).
      </HelpBanner>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <label className={label}>Nome *</label>
          <input className={field} value={v.name} onChange={(e) => set("name", e.target.value)} placeholder={isS3 ? "ex.: Data Lake Bronze" : "ex.: PostgreSQL Massa Teste"} required />
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

      {/* Alvo base */}
      <div className="border-t border-gray-100 pt-3">
        <span className={sectionTitle}>Alvo base (padrão reutilizável)</span>
        <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-2">
          {isS3 ? (
            <>
              <div><label className={label}>Bucket *</label><input className={field} value={v.target_bucket} onChange={(e) => set("target_bucket", e.target.value)} placeholder="datalake-t2c-data-integracao" /></div>
              <div><label className={label}>Camada *</label><input className={field} value={v.target_layer} onChange={(e) => set("target_layer", e.target.value)} placeholder="bronze / silver / gold" /></div>
              <div className="sm:col-span-2"><label className={label}>Prefixo base</label><input className={field} value={v.target_prefix} onChange={(e) => set("target_prefix", e.target.value)} placeholder="bronze  (o path relativo da tabela vem do Controle)" /></div>
              <div><label className={label}>Formato padrão *</label><select className={field} value={v.file_format} onChange={(e) => set("file_format", e.target.value)}>{FILE_FORMATS.map((f) => <option key={f} value={f}>{f}</option>)}</select></div>
              <div><label className={label}>Compressão padrão</label><select className={field} value={v.compression} onChange={(e) => set("compression", e.target.value)}>{COMPRESSIONS.map((c) => <option key={c} value={c}>{c}</option>)}</select></div>
              <div>
                <label className={label}>Criptografia (em repouso)</label>
                <select className={field} value={v.encryption_mode} onChange={(e) => set("encryption_mode", e.target.value)}>
                  <option value="SSE-S3">SSE-S3 (padrão)</option>
                  <option value="SSE-KMS">SSE-KMS (recomendado em produção)</option>
                </select>
              </div>
              {v.encryption_mode === "SSE-KMS" && (
                <div><label className={label}>KMS key id</label><input className={field} value={v.kms_key_id} onChange={(e) => set("kms_key_id", e.target.value)} placeholder="arn:aws:kms:... ou alias/minha-chave" /></div>
              )}
            </>
          ) : (
            <>
              <div><label className={label}>Database (opcional)</label><input className={field} value={v.target_database} onChange={(e) => set("target_database", e.target.value)} placeholder="andromeda" /></div>
              <div><label className={label}>Schema padrão *</label><input className={field} value={v.target_schema} onChange={(e) => set("target_schema", e.target.value)} placeholder="massa_teste" /></div>
              <div><label className={label}>Staging schema padrão</label><input className={field} value={v.staging_schema} onChange={(e) => set("staging_schema", e.target.value)} placeholder="(usa o schema padrão)" /></div>
            </>
          )}
          <div><label className={label}>Write mode padrão *</label><select className={field} value={v.write_mode} onChange={(e) => set("write_mode", e.target.value)}>{writeModes.map((m) => <option key={m} value={m}>{m}</option>)}</select></div>
        </div>
      </div>

      <div className="flex flex-wrap gap-4 border-t border-gray-100 pt-3">
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
