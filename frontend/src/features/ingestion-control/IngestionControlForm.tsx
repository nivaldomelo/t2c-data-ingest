import { useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { Page } from "@/lib/api";
import { PrimaryButton, SecondaryButton } from "@/components/ui";
import type { IngestionControl, S3DestinoConfig } from "@/features/ingestion-control/types";
import {
  COMPRESSION_VALUES,
  DESTINO_VALUES,
  FILE_FORMAT_VALUES,
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
    // Destino S3 / Data Lake
    destino_id: initial?.destino_id ?? "",
    target_bucket: initial?.destino_config?.target_bucket ?? "",
    target_prefix: initial?.destino_config?.target_prefix ?? "",
    target_layer: initial?.destino_config?.target_layer ?? "",
    file_format: initial?.destino_config?.file_format ?? "parquet",
    write_mode: initial?.destino_config?.write_mode ?? "append",
    partition_columns: initial?.destino_config?.partition_columns ?? "",
    compression: initial?.destino_config?.compression ?? "snappy",
  });
  const [error, setError] = useState<string | null>(null);

  const connections = useQuery({
    queryKey: ["connections-min"],
    queryFn: () => api.get<Page<ConnMin>>("/api/v1/connections?page=1&page_size=200"),
  });
  const conns = connections.data?.items ?? [];
  const isS3Destino = S3_DESTINOS.includes(String(v.destino));
  const writableS3 = conns.filter((c) => c.connection_type === "s3" && c.can_write);

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
      tipo_ingestao: s("tipo_ingestao"),
      coluna_data: s("coluna_data"),
      coluna_ultima_alteracao: s("coluna_ultima_alteracao"),
      colunas_chave: s("colunas_chave"),
      watermark_atual: dt("watermark_atual"),
      dados_sensiveis: s("dados_sensiveis"),
      status: s("status"),
      ultima_execucao: dt("ultima_execucao"),
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
        <div>
          <label className={label}>Origem</label>
          <select className={field} value={String(v.origem)} onChange={(e) => set("origem", e.target.value)}>{opt(ORIGEM_VALUES)}</select>
        </div>
        <div>
          <label className={label}>Destino</label>
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

      <Section title="4 · Segurança e sensibilidade">
        <div className="sm:col-span-2">
          <label className={label}>Dados sensíveis</label>
          <input className={field} value={String(v.dados_sensiveis)} onChange={(e) => set("dados_sensiveis", e.target.value)} placeholder="cpf,email,telefone" />
          <p className={hint}>Colunas sensíveis separadas por vírgula.</p>
        </div>
      </Section>

      <Section title="5 · Execução">
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
