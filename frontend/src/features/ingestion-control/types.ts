export interface IngestionControl {
  id: number;
  nome_tabela: string;
  coluna_data: string | null;
  coluna_ultima_alteracao: string | null;
  grupo: string | null;
  watermark_atual: string | null;
  ultima_execucao: string | null;
  status: string | null;
  observacao: string | null;
  ativo: boolean | null;
  criado_em: string | null;
  atualizado_em: string | null;
  tipo_tabela: string | null;
  origem: string | null;
  destino: string | null;
  dados_sensiveis: string | null;
  tipo_ingestao: string | null;
  colunas_chave: string | null;
  origem_id: string | null;
  destino_id: string | null;
  destino_config: S3DestinoConfig | null;
  destination_id: number | null;
  // CTRL-1 — descrição declarativa
  source_connection_id: number | null;
  target_connection_id: number | null;
  source_database: string | null;
  source_schema: string | null;
  source_table: string | null;
  source_query: string | null;
  source_path: string | null;
  source_file_format: string | null;
  target_database: string | null;
  target_schema: string | null;
  target_table: string | null;
  staging_schema: string | null;
  staging_table: string | null;
  target_bucket: string | null;
  target_prefix: string | null;
  target_path: string | null;
  target_layer: string | null;
  file_format: string | null;
  compression: string | null;
  partition_columns: string[] | null;
  write_mode: string | null;
  upsert_strategy: string | null;
  truncate_before_load: boolean | null;
  expected_frequency: string | null;
  expected_frequency_minutes: number | null;
  owner_name: string | null;
  owner_email: string | null;
  sla_minutes: number | null;
  criticality: string | null;
  extra_params: Record<string, unknown> | null;
  source: Record<string, unknown> | null;
  target: Record<string, unknown> | null;
}

/** Configuração de destino S3 / Data Lake (sem segredos — credenciais ficam na conexão). */
export interface S3DestinoConfig {
  target_bucket?: string;
  target_prefix?: string;
  target_layer?: string;
  file_format?: string;
  write_mode?: string;
  partition_columns?: string;
  compression?: string;
}

export interface IngestionControlSummary {
  total: number;
  ativas: number;
  inativas: number;
  incrementais: number;
  ultimas_com_erro: number;
}

export const STATUS_VALUES = ["PENDENTE", "ATIVO", "EM_EXECUCAO", "SUCESSO", "ERRO", "INATIVO", "PAUSADO"];
export const TIPO_TABELA_VALUES = ["FULL", "INCREMENTAL", "DIMENSAO", "FATO", "CONTROLE", "LOG"];
export const TIPO_INGESTAO_VALUES = ["FULL", "INCREMENTAL", "CDC", "D-1", "MANUAL"];
export const ORIGEM_VALUES = ["MYSQL", "POSTGRES", "SQLSERVER", "ORACLE", "API", "S3", "CSV", "PARQUET"];
export const DESTINO_VALUES = ["BRONZE", "SILVER", "GOLD", "POSTGRES", "S3", "DATALAKE"];

/** Destinos que gravam no Data Lake e habilitam a configuração S3. */
export const S3_DESTINOS = ["S3", "DATALAKE", "BRONZE", "SILVER", "GOLD"];
export const FILE_FORMAT_VALUES = ["parquet", "csv", "json", "orc", "avro", "delta"];
export const WRITE_MODE_VALUES = ["append", "overwrite", "overwrite_partitions", "truncate_insert", "upsert"];
export const COMPRESSION_VALUES = ["snappy", "gzip", "zstd", "lz4", "none"];
export const FREQUENCY_VALUES = ["15min", "30min", "hourly", "2_hours", "daily", "weekly", "monthly", "manual"];
export const CRITICALITY_VALUES = ["baixa", "media", "alta", "critica"];

export function fmtDate(t: string | null | undefined): string {
  return t ? new Date(t).toLocaleString("pt-BR") : "—";
}
