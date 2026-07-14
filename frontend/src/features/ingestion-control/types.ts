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
export const WRITE_MODE_VALUES = ["append", "overwrite", "ignore", "errorifexists"];
export const COMPRESSION_VALUES = ["snappy", "gzip", "zstd", "lz4", "none"];

export function fmtDate(t: string | null | undefined): string {
  return t ? new Date(t).toLocaleString("pt-BR") : "—";
}
