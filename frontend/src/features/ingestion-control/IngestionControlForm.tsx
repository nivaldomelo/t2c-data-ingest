import { useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { Page } from "@/lib/api";
import { PrimaryButton, SecondaryButton } from "@/components/ui";
import type { IngestionControl, S3DestinoConfig } from "@/features/ingestion-control/types";
import {
  COMPRESSION_VALUES,
  CRITICALITY_VALUES,
  DESTINO_VALUES,
  FILE_FORMAT_VALUES,
  FREQUENCY_VALUES,
  ORIGEM_VALUES,
  S3_DESTINOS,
  STATUS_VALUES,
  TIPO_INGESTAO_VALUES,
  TIPO_TABELA_VALUES,
  WRITE_MODE_VALUES,
} from "@/features/ingestion-control/types";

interface ConnMin {
  id: number;
  name: string;
  connection_type: string;
  can_read?: boolean;
  can_write?: boolean;
  extra_params?: { bucket_name?: string; base_prefix?: string; default_layer?: string } | null;
}

export type ControlPayload = Partial<IngestionControl> & { nome_tabela: string };

const label = "block text-sm font-medium text-gray-700";
const hint = "mt-1 text-xs text-gray-400";
const field =
  "mt-1.5 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-500/20";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="border-t border-gray-100 pt-4 first:border-0 first:pt-0">
      <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-brand-600">{title}</h3>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">{children}</div>
    </div>
  );
}

function toLocal(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

export function IngestionControlForm({
  initial,
  canEditExecution,
  saving,
  onSubmit,
  onCancel,
}: {
  initial: IngestionControl | null;
  canEditExecution: boolean;
  saving?: boolean;
  onSubmit: (payload: ControlPayload) => void;
  onCancel: () => void;
}) {
  const [v, setV] = useState<Record<string, string | boolean>>({
    nome_tabela: initial?.nome_tabela ?? "",
    grupo: initial?.grupo ?? "",
    tipo_tabela: initial?.tipo_tabela ?? "",
    ativo: initial?.ativo ?? true,
    observacao: initial?.observacao ?? "",
    origem: initial?.origem ?? "",
    origem_id: initial?.origem_id ?? "",
    destino: initial?.destino ?? "",
    tipo_ingestao: initial?.tipo_ingestao ?? "",
    coluna_data: initial?.coluna_data ?? "",
    coluna_ultima_alteracao: initial?.coluna_ultima_alteracao ?? "",
    colunas_chave: initial?.colunas_chave ?? "",
    watermark_atual: toLocal(initial?.watermark_atual),
    dados_sensiveis: initial?.dados_sensiveis ?? "",
    status: initial?.status ?? "",
    ultima_execucao: toLocal(initial?.ultima_execucao),
    // Destino configurável (DEST-1) + config S3 legada
    destination_id: initial?.destination_id != null ? String(initial.destination_id) : "",
    destino_id: initial?.destino_id ?? "",
    // Destino S3 (first-class no controle; fallback ao destino_config legado).
    target_bucket: initial?.target_bucket ?? initial?.destino_config?.target_bucket ?? "",
    target_prefix: initial?.target_prefix ?? initial?.destino_config?.target_prefix ?? "",
    target_layer: initial?.target_layer ?? initial?.destino_config?.target_layer ?? "",
    file_format: initial?.file_format ?? initial?.destino_config?.file_format ?? "parquet",
    write_mode: initial?.write_mode ?? initial?.destino_config?.write_mode ?? "append",
    partition_columns: (initial?.partition_columns ?? []).join(",") || (initial?.destino_config?.partition_columns ?? ""),
    compression: initial?.compression ?? initial?.destino_config?.compression ?? "snappy",
    // CTRL-1: origem/destino por conexão + destino manual (banco) + SLA/owner
    source_connection_id: initial?.source_connection_id != null ? String(initial.source_connection_id) : "",
    source_schema: initial?.source_schema ?? "",
    source_table: initial?.source_table ?? "",
    source_query: initial?.source_query ?? "",
    target_connection_id: initial?.target_connection_id != null ? String(initial.target_connection_id) : "",
    target_schema: initial?.target_schema ?? "",
    target_table: initial?.target_table ?? "",
    staging_schema: initial?.staging_schema ?? "",
    staging_table: initial?.staging_table ?? "",
    upsert_strategy: initial?.upsert_strategy ?? "",
    truncate_before_load: initial?.truncate_before_load ?? false,
    owner_name: initial?.owner_name ?? "",
    owner_email: initial?.owner_email ?? "",
    expected_frequency: initial?.expected_frequency ?? "",
    sla_minutes: initial?.sla_minutes != null ? String(initial.sla_minutes) : "",
    criticality: initial?.criticality ?? "",
  });
  const [error, setError] = useState<string | null>(null);

  const connections = useQuery({
    queryKey: ["connections-min"],
    queryFn: () => api.get<Page<ConnMin>>("/api/v1/connections?page=1&page_size=200"),
  });
  const conns = connections.data?.items ?? [];
  const isS3Destino = S3_DESTINOS.includes(String(v.destino));
  const writableS3 = conns.filter((c) => c.connection_type === "s3" && c.can_write);

  // Destinos configuráveis (DEST-1) — destino real da carga.
  const destinations = useQuery({
    queryKey: ["destinations-min"],
    queryFn: () => api.get<Page<{ id: number; name: string; destination_type: string; target_display: string | null }>>(
      "/api/v1/destinations?page=1&page_size=200&active=true"),
  });
  const destItems = destinations.data?.items ?? [];

  function set(k: string, val: string | boolean) {
    setV((p) => ({ ...p, [k]: val }));
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!String(v.nome_tabela).trim()) return setError("Nome da tabela é obrigatório.");
    if (v.tipo_ingestao === "INCREMENTAL" && !v.coluna_ultima_alteracao && !v.coluna_data) {
      setError("Para ingestão INCREMENTAL, recomenda-se preencher coluna de data ou de última alteração.");
      return;
    }
    const s = (k: string) => {
      const val = String(v[k] ?? "").trim();
      return val === "" ? null : val;
    };
    const dt = (k: string) => (v[k] ? new Date(String(v[k])).toISOString() : null);

    // Configuração de destino S3 apenas quando o destino é Data Lake (senão limpa).
    let destinoConfig: S3DestinoConfig | null = null;
    if (isS3Destino) {
      const prefix = String(v.target_prefix ?? "").trim().replace(/^\/+|\/+$/g, "");
      if (prefix.split("/").includes("..")) {
        setError("O prefixo de destino não pode conter '..'.");
        return;
      }
      const cfg: S3DestinoConfig = {
        target_bucket: s("target_bucket") ?? undefined,
        target_prefix: prefix || undefined,
        target_layer: s("target_layer") ?? undefined,
        file_format: s("file_format") ?? undefined,
        write_mode: s("write_mode") ?? undefined,
        partition_columns: s("partition_columns") ?? undefined,
        compression: s("compression") ?? undefined,
      };
      destinoConfig = Object.values(cfg).some((x) => x != null) ? cfg : null;
    }

    const list = (k: string) => {
      const arr = String(v[k] ?? "").split(",").map((x) => x.trim()).filter(Boolean);
      return arr.length ? arr : null;
    };
    const num = (k: string) => { const val = String(v[k] ?? "").trim(); return val ? Number(val) : null; };

    onSubmit({
      nome_tabela: String(v.nome_tabela).trim(),
      grupo: s("grupo"),
      tipo_tabela: s("tipo_tabela"),
      ativo: !!v.ativo,
      observacao: s("observacao"),
      origem: s("origem"),
      origem_id: s("origem_id"),
      destino: s("destino"),
      destino_id: s("destino_id"),
      destino_config: destinoConfig,
      destination_id: v.destination_id ? Number(v.destination_id) : null,
      tipo_ingestao: s("tipo_ingestao"),
      coluna_data: s("coluna_data"),
      coluna_ultima_alteracao: s("coluna_ultima_alteracao"),
      colunas_chave: s("colunas_chave"),
      watermark_atual: dt("watermark_atual"),
      dados_sensiveis: s("dados_sensiveis"),
      status: s("status"),
      ultima_execucao: dt("ultima_execucao"),
      // ── CTRL-1: descrição declarativa (first-class) ──
      source_connection_id: num("source_connection_id"),
      source_schema: s("source_schema"),
      source_table: s("source_table"),
      source_query: s("source_query"),
      target_connection_id: num("target_connection_id"),
      target_schema: s("target_schema"),
      target_table: s("target_table"),
      staging_schema: s("staging_schema"),
      staging_table: s("staging_table"),
      upsert_strategy: s("upsert_strategy"),
      truncate_before_load: !!v.truncate_before_load,
      write_mode: s("write_mode"),
      // destino S3 first-class (além do destino_config legado, para o runner/resolver)
      target_bucket: isS3Destino ? s("target_bucket") : null,
      target_prefix: isS3Destino ? s("target_prefix") : null,
      target_layer: isS3Destino ? s("target_layer") : null,
      file_format: isS3Destino ? s("file_format") : null,
      compression: isS3Destino ? s("compression") : null,
      partition_columns: isS3Destino ? list("partition_columns") : null,
      owner_name: s("owner_name"),
      owner_email: s("owner_email"),
      expected_frequency: s("expected_frequency"),
      sla_minutes: num("sla_minutes"),
      criticality: s("criticality"),
    });
  }

  const opt = (vals: string[]) => [<option key="" value="">—</option>, ...vals.map((x) => <option key={x} value={x}>{x}</option>)];

  return (
    <form onSubmit={submit} className="space-y-5">
      <Section title="1 · Identificação">
        <div className="sm:col-span-2">
          <label className={label}>Nome da tabela *</label>
          <input className={field} value={String(v.nome_tabela)} onChange={(e) => set("nome_tabela", e.target.value)} placeholder="ex.: software_test_lab.payments" />
        </div>
        <div>
          <label className={label}>Grupo</label>
          <input className={field} value={String(v.grupo)} onChange={(e) => set("grupo", e.target.value)} />
        </div>
        <div>
          <label className={label}>Tipo da tabela</label>
          <select className={field} value={String(v.tipo_tabela)} onChange={(e) => set("tipo_tabela", e.target.value)}>{opt(TIPO_TABELA_VALUES)}</select>
        </div>
        <div className="sm:col-span-2">
          <label className={label}>Observação</label>
          <input className={field} value={String(v.observacao)} onChange={(e) => set("observacao", e.target.value)} />
        </div>
        <label className="flex items-center gap-2 text-sm text-gray-700">
          <input type="checkbox" className="h-4 w-4 rounded border-gray-300 text-brand-500 focus:ring-brand-500/30" checked={!!v.ativo} onChange={(e) => set("ativo", e.target.checked)} />
          Ativo
        </label>
      </Section>

      <Section title="2 · Origem e destino">
        <div className="sm:col-span-2">
          <label className={label}>Destino configurável</label>
          <select className={field} value={String(v.destination_id)} onChange={(e) => set("destination_id", e.target.value)}>
            <option value="">— Nenhum (usar rótulo/legado) —</option>
            {destItems.map((d) => (
              <option key={d.id} value={String(d.id)}>{d.name} · {d.destination_type} · {d.target_display}</option>
            ))}
          </select>
          <p className={hint}>Destino real da carga (entidade Destinos). Se preenchido, tem prioridade sobre os campos manuais abaixo.</p>
        </div>
        <div>
          <label className={label}>Conexão de origem</label>
          <select className={field} value={String(v.source_connection_id)} onChange={(e) => set("source_connection_id", e.target.value)}>
            <option value="">— Selecione —</option>
            {conns.map((c) => <option key={c.id} value={String(c.id)}>{c.name} ({c.connection_type})</option>)}
          </select>
        </div>
        <div>
          <label className={label}>Conexão de destino (manual)</label>
          <select className={field} value={String(v.target_connection_id)} onChange={(e) => set("target_connection_id", e.target.value)}>
            <option value="">— Selecione (ou use Destino configurável) —</option>
            {conns.map((c) => <option key={c.id} value={String(c.id)}>{c.name} ({c.connection_type})</option>)}
          </select>
        </div>
        <div>
          <label className={label}>Schema origem</label>
          <input className={field} value={String(v.source_schema)} onChange={(e) => set("source_schema", e.target.value)} placeholder="ex.: massa_teste" />
        </div>
        <div>
          <label className={label}>Tabela origem</label>
          <input className={field} value={String(v.source_table)} onChange={(e) => set("source_table", e.target.value)} placeholder="ex.: eventos_status" />
        </div>
        <div className="sm:col-span-2">
          <label className={label}>Query de origem (opcional)</label>
          <input className={field} value={String(v.source_query)} onChange={(e) => set("source_query", e.target.value)} placeholder="SELECT ... (substitui schema/tabela)" />
        </div>
        <div>
          <label className={label}>Origem (rótulo)</label>
          <select className={field} value={String(v.origem)} onChange={(e) => set("origem", e.target.value)}>{opt(ORIGEM_VALUES)}</select>
        </div>
        <div>
          <label className={label}>Destino (rótulo/camada)</label>
          <select className={field} value={String(v.destino)} onChange={(e) => set("destino", e.target.value)}>{opt(DESTINO_VALUES)}</select>
        </div>
        <div className="sm:col-span-2">
          <label className={label}>Origem ID (conexão)</label>
          <div className="flex gap-2">
            <input className={`${field} flex-1`} value={String(v.origem_id)} onChange={(e) => set("origem_id", e.target.value)} placeholder="id ou identificador da origem" />
            <select
              className={`${field} w-56 shrink-0`}
              value=""
              onChange={(e) => e.target.value && set("origem_id", e.target.value)}
              title="Usar uma conexão cadastrada"
            >
              <option value="">Usar conexão…</option>
              {conns.map((c) => (
                <option key={c.id} value={String(c.id)}>{c.name} ({c.connection_type})</option>
              ))}
            </select>
          </div>
          <p className={hint}>Preencha manualmente ou selecione uma conexão cadastrada (salva o id da conexão).</p>
        </div>

        {isS3Destino && (
          <div className="sm:col-span-2">
            <label className={label}>Conexão de destino (S3 / Data Lake)</label>
            <select
              className={field}
              value={String(v.destino_id)}
              onChange={(e) => {
                const id = e.target.value;
                set("destino_id", id);
                // Pré-preenche bucket/prefixo/camada com os defaults da conexão selecionada.
                const c = writableS3.find((x) => String(x.id) === id);
                if (c?.extra_params) {
                  if (!String(v.target_bucket).trim() && c.extra_params.bucket_name) set("target_bucket", c.extra_params.bucket_name);
                  if (!String(v.target_prefix).trim() && c.extra_params.base_prefix) set("target_prefix", c.extra_params.base_prefix);
                  if (!String(v.target_layer).trim() && c.extra_params.default_layer) set("target_layer", c.extra_params.default_layer);
                }
              }}
            >
              <option value="">Selecione uma conexão S3 com escrita…</option>
              {writableS3.map((c) => (
                <option key={c.id} value={String(c.id)}>{c.name}</option>
              ))}
            </select>
            <p className={hint}>
              Apenas conexões S3 com escrita habilitada aparecem aqui. As credenciais ficam na conexão — nunca neste controle.
            </p>
          </div>
        )}
      </Section>

      {isS3Destino && (
        <Section title="2b · Destino S3 / Data Lake">
          <div>
            <label className={label}>Bucket</label>
            <input className={field} value={String(v.target_bucket)} onChange={(e) => set("target_bucket", e.target.value)} placeholder="ex.: t2c-datalake" />
            <p className={hint}>Vazio usa o bucket padrão da conexão.</p>
          </div>
          <div>
            <label className={label}>Prefixo de destino</label>
            <input className={field} value={String(v.target_prefix)} onChange={(e) => set("target_prefix", e.target.value)} placeholder="ex.: bronze/vendas" />
          </div>
          <div>
            <label className={label}>Camada (layer)</label>
            <input className={field} value={String(v.target_layer)} onChange={(e) => set("target_layer", e.target.value)} placeholder="bronze / silver / gold" />
          </div>
          <div>
            <label className={label}>Formato do arquivo</label>
            <select className={field} value={String(v.file_format)} onChange={(e) => set("file_format", e.target.value)}>{opt(FILE_FORMAT_VALUES)}</select>
          </div>
          <div>
            <label className={label}>Modo de escrita</label>
            <select className={field} value={String(v.write_mode)} onChange={(e) => set("write_mode", e.target.value)}>{opt(WRITE_MODE_VALUES)}</select>
          </div>
          <div>
            <label className={label}>Compressão</label>
            <select className={field} value={String(v.compression)} onChange={(e) => set("compression", e.target.value)}>{opt(COMPRESSION_VALUES)}</select>
          </div>
          <div className="sm:col-span-2">
            <label className={label}>Colunas de partição</label>
            <input className={field} value={String(v.partition_columns)} onChange={(e) => set("partition_columns", e.target.value)} placeholder="ex.: ano,mes,dia" />
            <p className={hint}>Separadas por vírgula. Padrão do Data Lake: ano/mes/dia.</p>
          </div>
        </Section>
      )}

      {!isS3Destino && !v.destination_id && (
        <Section title="2b · Destino banco (manual)">
          <div><label className={label}>Schema destino</label><input className={field} value={String(v.target_schema)} onChange={(e) => set("target_schema", e.target.value)} placeholder="ex.: spark" /></div>
          <div><label className={label}>Tabela destino</label><input className={field} value={String(v.target_table)} onChange={(e) => set("target_table", e.target.value)} placeholder="(vazio = usa nome_tabela)" /></div>
          <div><label className={label}>Modo de escrita</label><select className={field} value={String(v.write_mode)} onChange={(e) => set("write_mode", e.target.value)}>{opt(WRITE_MODE_VALUES)}</select></div>
          <div><label className={label}>Upsert strategy</label><input className={field} value={String(v.upsert_strategy)} onChange={(e) => set("upsert_strategy", e.target.value)} placeholder="on_conflict / merge" /></div>
          <div><label className={label}>Schema staging</label><input className={field} value={String(v.staging_schema)} onChange={(e) => set("staging_schema", e.target.value)} /></div>
          <div><label className={label}>Tabela staging</label><input className={field} value={String(v.staging_table)} onChange={(e) => set("staging_table", e.target.value)} placeholder="stg_..." /></div>
          <label className="flex items-center gap-2 text-sm text-gray-700 sm:col-span-2">
            <input type="checkbox" className="h-4 w-4 rounded border-gray-300 text-brand-500 focus:ring-brand-500/30" checked={!!v.truncate_before_load} onChange={(e) => set("truncate_before_load", e.target.checked)} />
            Truncar antes de carregar
          </label>
        </Section>
      )}

      <Section title="3 · Estratégia de ingestão">
        <div>
          <label className={label}>Tipo de ingestão</label>
          <select className={field} value={String(v.tipo_ingestao)} onChange={(e) => set("tipo_ingestao", e.target.value)}>{opt(TIPO_INGESTAO_VALUES)}</select>
        </div>
        <div>
          <label className={label}>Watermark atual</label>
          <input type="datetime-local" className={field} value={String(v.watermark_atual)} onChange={(e) => set("watermark_atual", e.target.value)} />
          <p className={hint}>Último ponto de controle da ingestão incremental. Edite com cuidado.</p>
        </div>
        <div>
          <label className={label}>Coluna de data</label>
          <input className={field} value={String(v.coluna_data)} onChange={(e) => set("coluna_data", e.target.value)} />
          <p className={hint}>Coluna usada para filtro por data.</p>
        </div>
        <div>
          <label className={label}>Coluna de última alteração</label>
          <input className={field} value={String(v.coluna_ultima_alteracao)} onChange={(e) => set("coluna_ultima_alteracao", e.target.value)} />
          <p className={hint}>Usada para incremental/update.</p>
        </div>
        <div className="sm:col-span-2">
          <label className={label}>Colunas chave</label>
          <input className={field} value={String(v.colunas_chave)} onChange={(e) => set("colunas_chave", e.target.value)} placeholder="id  ou  id,order_id" />
          <p className={hint}>Colunas para merge/upsert, separadas por vírgula.</p>
        </div>
      </Section>

      <Section title="4 · SLA e ownership">
        <div>
          <label className={label}>Owner</label>
          <input className={field} value={String(v.owner_name)} onChange={(e) => set("owner_name", e.target.value)} placeholder="ex.: Engenharia de Dados" />
        </div>
        <div>
          <label className={label}>Owner e-mail</label>
          <input className={field} value={String(v.owner_email)} onChange={(e) => set("owner_email", e.target.value)} placeholder="data@turn2c.com" />
        </div>
        <div>
          <label className={label}>Frequência esperada</label>
          <select className={field} value={String(v.expected_frequency)} onChange={(e) => set("expected_frequency", e.target.value)}>{opt(FREQUENCY_VALUES)}</select>
        </div>
        <div>
          <label className={label}>SLA (minutos)</label>
          <input type="number" min={0} className={field} value={String(v.sla_minutes)} onChange={(e) => set("sla_minutes", e.target.value)} placeholder="ex.: 60" />
        </div>
        <div>
          <label className={label}>Criticidade</label>
          <select className={field} value={String(v.criticality)} onChange={(e) => set("criticality", e.target.value)}>{opt(CRITICALITY_VALUES)}</select>
        </div>
      </Section>

      <Section title="5 · Segurança e sensibilidade">
        <div className="sm:col-span-2">
          <label className={label}>Dados sensíveis</label>
          <input className={field} value={String(v.dados_sensiveis)} onChange={(e) => set("dados_sensiveis", e.target.value)} placeholder="cpf,email,telefone" />
          <p className={hint}>Colunas sensíveis separadas por vírgula.</p>
        </div>
      </Section>

      <Section title="6 · Execução">
        <div>
          <label className={label}>Status</label>
          <select className={field} value={String(v.status)} onChange={(e) => set("status", e.target.value)}>{opt(STATUS_VALUES)}</select>
        </div>
        <div>
          <label className={label}>Última execução</label>
          <input type="datetime-local" className={field} value={String(v.ultima_execucao)} disabled={!canEditExecution} onChange={(e) => set("ultima_execucao", e.target.value)} />
          {!canEditExecution && <p className={hint}>Somente leitura.</p>}
        </div>
      </Section>

      {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

      <div className="flex items-center justify-end gap-2 border-t border-gray-100 pt-4">
        <SecondaryButton type="button" onClick={onCancel}>Cancelar</SecondaryButton>
        <PrimaryButton type="submit" loading={saving}>Salvar</PrimaryButton>
      </div>
    </form>
  );
}
