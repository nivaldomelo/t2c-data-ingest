import { useMemo, useState } from "react";
import type { FormEvent } from "react";

import { PrimaryButton, SecondaryButton } from "@/components/ui";
import { ConnectionTestResult as TestResultView } from "@/features/connections/ConnectionTestResult";
import type {
  Connection,
  ConnectionFormValues,
  ConnectionTestResult,
  ConnectionType,
  S3AuthMode,
  S3ExtraParams,
} from "@/features/connections/types";
import { DEFAULT_PORTS, S3_AUTH_MODE_LABEL } from "@/features/connections/types";

export interface ConnectionSubmitPayload {
  name: string;
  description: string | null;
  connection_type: ConnectionType;
  host: string | null;
  port: number | null;
  database_name: string | null;
  username: string | null;
  password?: string;
  schema_name: string | null;
  ssl_enabled: boolean;
  active: boolean;
  can_read: boolean;
  can_write: boolean;
  extra_params: Record<string, unknown> | null;
  // S3 secrets (write-only; empty keeps the current value on edit)
  aws_access_key_id?: string;
  aws_secret_access_key?: string;
  aws_session_token?: string;
  // Generic type-specific secrets (API tokens, client_secret, …), write-only.
  secrets?: Record<string, string>;
}

function s3Extra(c: Connection | null): S3ExtraParams {
  return (c?.extra_params ?? {}) as S3ExtraParams;
}

function toValues(c: Connection | null, forced?: string): ConnectionFormValues {
  const type = c?.connection_type ?? forced ?? "postgres";
  const ep = s3Extra(c);
  return {
    name: c?.name ?? "",
    description: c?.description ?? "",
    connection_type: type,
    host: c?.host ?? "",
    port: c?.port ?? DEFAULT_PORTS[type] ?? "",
    database_name: c?.database_name ?? "",
    username: c?.username ?? "",
    password: "",
    schema_name: c?.schema_name ?? "",
    ssl_enabled: c ? c.ssl_enabled : type === "s3",
    active: c?.active ?? true,
    can_read: c?.can_read ?? true,
    can_write: c?.can_write ?? false,
    extra_params:
      type !== "s3" && c?.extra_params ? JSON.stringify(c.extra_params, null, 2) : "",
    // S3
    aws_region: ep.aws_region ?? "",
    bucket_name: ep.bucket_name ?? "",
    base_prefix: ep.base_prefix ?? "",
    default_layer: ep.default_layer ?? "",
    auth_mode: (ep.auth_mode as S3AuthMode) ?? "access_key",
    endpoint_url: ep.endpoint_url ?? "",
    role_arn: ep.role_arn ?? "",
    external_id: ep.external_id ?? "",
    aws_access_key_id: "",
    aws_secret_access_key: "",
    aws_session_token: "",
    catalog_enabled: !!ep.catalog_enabled,
    catalog_mode: ep.catalog_mode ?? "layer_as_schema",
  };
}

const label = "block text-sm font-medium text-gray-700";
const field =
  "mt-1.5 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-500/20";
const sectionTitle = "text-xs font-semibold uppercase tracking-wide text-gray-400";

export function ConnectionForm({
  initial,
  forcedType,
  saving,
  testResult,
  onSubmit,
  onCancel,
}: {
  initial: Connection | null;
  forcedType?: string;
  saving?: boolean;
  testResult?: ConnectionTestResult | null;
  onSubmit: (payload: ConnectionSubmitPayload, testAfter: boolean) => void;
  onCancel: () => void;
}) {
  const [v, setV] = useState<ConnectionFormValues>(() => toValues(initial, forcedType));
  const [error, setError] = useState<string | null>(null);
  const isEdit = !!initial;
  const isS3 = v.connection_type === "s3";
  const showKeys = isS3 && v.auth_mode === "access_key";
  const showRole = isS3 && v.auth_mode === "iam_role";

  function set<K extends keyof ConnectionFormValues>(key: K, value: ConnectionFormValues[K]) {
    setV((prev) => ({ ...prev, [key]: value }));
  }

  function changeType(type: ConnectionType) {
    setV((prev) => ({
      ...prev,
      connection_type: type,
      // Sugere a porta padrão quando vazia ou igual à porta padrão do tipo anterior.
      port:
        type === "s3"
          ? ""
          : prev.port === "" || prev.port === DEFAULT_PORTS[prev.connection_type]
            ? DEFAULT_PORTS[type] ?? ""
            : prev.port,
      // S3 usa SSL por padrão (HTTPS na AWS).
      ssl_enabled: type === "s3" ? true : prev.ssl_enabled,
    }));
  }

  const canSubmit = useMemo(
    () => v.name.trim().length > 0 && (!isS3 || v.bucket_name.trim().length > 0),
    [v.name, v.bucket_name, isS3],
  );

  function build(): ConnectionSubmitPayload | null {
    const base: ConnectionSubmitPayload = {
      name: v.name.trim(),
      description: v.description.trim() || null,
      connection_type: v.connection_type,
      host: null,
      port: null,
      database_name: null,
      username: null,
      schema_name: null,
      ssl_enabled: v.ssl_enabled,
      active: v.active,
      can_read: v.can_read,
      can_write: v.can_write,
      extra_params: null,
    };

    if (isS3) {
      const bucket = v.bucket_name.trim();
      if (!bucket) {
        setError("Informe o nome do bucket.");
        return null;
      }
      const prefix = v.base_prefix.trim().replace(/^\/+|\/+$/g, "");
      if (prefix.split("/").includes("..")) {
        setError("O prefixo base não pode conter '..'.");
        return null;
      }
      const extra: S3ExtraParams = {
        aws_region: v.aws_region.trim() || undefined,
        bucket_name: bucket,
        base_prefix: prefix || undefined,
        default_layer: v.default_layer.trim() || undefined,
        auth_mode: v.auth_mode,
        endpoint_url: v.endpoint_url.trim() || undefined,
        ssl_enabled: v.ssl_enabled,
      };
      if (showRole) {
        extra.role_arn = v.role_arn.trim() || undefined;
        extra.external_id = v.external_id.trim() || undefined;
      }
      if (v.catalog_enabled) {
        extra.catalog_enabled = true;
        extra.catalog_mode = v.catalog_mode;
        extra.default_file_format = "parquet";
        // Sem camadas explícitas: o backend usa o bucket/prefixo desta conexão como um schema.
        if (v.catalog_mode === "layer_as_schema") {
          extra.layers = [{ name: (v.default_layer.trim() || "datalake"), bucket, base_prefix: prefix || undefined }];
        }
      }
      base.extra_params = extra as Record<string, unknown>;
      // Secrets só quando preenchidos (vazio mantém o atual no modo edição).
      if (showKeys) {
        if (v.aws_access_key_id.trim()) base.aws_access_key_id = v.aws_access_key_id.trim();
        if (v.aws_secret_access_key) base.aws_secret_access_key = v.aws_secret_access_key;
        if (v.aws_session_token) base.aws_session_token = v.aws_session_token;
      }
      return base;
    }

    // Banco de dados relacional
    let extra: Record<string, unknown> | null = null;
    if (v.extra_params.trim()) {
      try {
        extra = JSON.parse(v.extra_params);
      } catch {
        setError("Parâmetros extras devem ser um JSON válido.");
        return null;
      }
    }
    base.host = v.host.trim() || null;
    base.port = v.port === "" ? null : Number(v.port);
    base.database_name = v.database_name.trim() || null;
    base.username = v.username.trim() || null;
    base.schema_name = v.schema_name.trim() || null;
    base.extra_params = extra;
    if (v.password) base.password = v.password;
    return base;
  }

  function submit(e: FormEvent, testAfter: boolean) {
    e.preventDefault();
    setError(null);
    const payload = build();
    if (!payload) return;
    onSubmit(payload, testAfter);
  }

  return (
    <form onSubmit={(e) => submit(e, false)}>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {/* ── Identificação ── */}
        <div className="sm:col-span-2">
          <label className={label}>Nome da conexão *</label>
          <input className={field} value={v.name} onChange={(e) => set("name", e.target.value)} placeholder={isS3 ? "ex.: datalake_prod" : "ex.: bd_clientes_prod"} required />
        </div>
        <div className="sm:col-span-2">
          <label className={label}>Descrição</label>
          <input className={field} value={v.description} onChange={(e) => set("description", e.target.value)} placeholder="Para que serve esta conexão" />
        </div>
        {!forcedType && (
          <div className={isS3 ? "sm:col-span-2" : ""}>
            <label className={label}>Tipo *</label>
            <select className={field} value={v.connection_type} onChange={(e) => changeType(e.target.value as ConnectionType)}>
              <option value="postgres">PostgreSQL</option>
              <option value="mysql">MySQL</option>
              <option value="s3">AWS S3 / Data Lake</option>
            </select>
          </div>
        )}

        {!isS3 && (
          <>
            <div>
              <label className={label}>Porta</label>
              <input
                type="number"
                className={field}
                value={v.port}
                onChange={(e) => set("port", e.target.value === "" ? "" : Number(e.target.value))}
                placeholder={String(DEFAULT_PORTS[v.connection_type] ?? "")}
              />
            </div>
            <div className="sm:col-span-2">
              <label className={label}>Host</label>
              <input className={field} value={v.host} onChange={(e) => set("host", e.target.value)} placeholder="ex.: db.empresa.com" />
            </div>
            <div>
              <label className={label}>Banco</label>
              <input className={field} value={v.database_name} onChange={(e) => set("database_name", e.target.value)} />
            </div>
            <div>
              <label className={label}>Schema</label>
              <input className={field} value={v.schema_name} onChange={(e) => set("schema_name", e.target.value)} placeholder="public" />
            </div>
            <div>
              <label className={label}>Usuário</label>
              <input className={field} value={v.username} onChange={(e) => set("username", e.target.value)} autoComplete="off" />
            </div>
            <div>
              <label className={label}>Senha</label>
              <input
                type="password"
                className={field}
                value={v.password}
                onChange={(e) => set("password", e.target.value)}
                autoComplete="new-password"
                placeholder={isEdit && initial?.has_password ? "•••••••• (mantém a atual)" : "senha do banco"}
              />
              {isEdit && initial?.has_password && (
                <p className="mt-1 text-xs text-gray-400">Deixe em branco para manter a senha já cadastrada.</p>
              )}
            </div>
            <div className="sm:col-span-2">
              <label className={label}>Parâmetros extras (JSON)</label>
              <textarea
                className={`${field} h-20 font-mono text-xs`}
                value={v.extra_params}
                onChange={(e) => set("extra_params", e.target.value)}
                placeholder='{"sslrootcert": "/certs/ca.pem"}'
              />
            </div>
          </>
        )}

        {isS3 && (
          <>
            {/* ── Localização ── */}
            <div className="sm:col-span-2 mt-2 border-t border-gray-100 pt-4">
              <span className={sectionTitle}>Localização</span>
            </div>
            <div>
              <label className={label}>Bucket *</label>
              <input className={field} value={v.bucket_name} onChange={(e) => set("bucket_name", e.target.value)} placeholder="ex.: t2c-datalake" required />
            </div>
            <div>
              <label className={label}>Região (AWS region)</label>
              <input className={field} value={v.aws_region} onChange={(e) => set("aws_region", e.target.value)} placeholder="ex.: us-east-1" />
            </div>
            <div>
              <label className={label}>Prefixo base</label>
              <input className={field} value={v.base_prefix} onChange={(e) => set("base_prefix", e.target.value)} placeholder="ex.: bronze/vendas" />
            </div>
            <div>
              <label className={label}>Camada padrão (layer)</label>
              <input className={field} value={v.default_layer} onChange={(e) => set("default_layer", e.target.value)} placeholder="ex.: bronze / silver / gold" />
            </div>
            <div className="sm:col-span-2">
              <label className={label}>Endpoint (S3-compatível — deixe vazio para AWS)</label>
              <input className={field} value={v.endpoint_url} onChange={(e) => set("endpoint_url", e.target.value)} placeholder="ex.: http://minio:9000 (MinIO/on-prem)" />
            </div>

            {/* ── Autenticação ── */}
            <div className="sm:col-span-2 mt-2 border-t border-gray-100 pt-4">
              <span className={sectionTitle}>Autenticação</span>
            </div>
            <div className="sm:col-span-2">
              <label className={label}>Modo de autenticação</label>
              <select className={field} value={v.auth_mode} onChange={(e) => set("auth_mode", e.target.value as S3AuthMode)}>
                {(Object.keys(S3_AUTH_MODE_LABEL) as S3AuthMode[]).map((m) => (
                  <option key={m} value={m}>{S3_AUTH_MODE_LABEL[m]}</option>
                ))}
              </select>
              <p className="mt-1 text-xs text-gray-400">
                Em produção prefira <span className="font-medium">IAM Role</span> ou <span className="font-medium">Instance Profile</span> — sem chaves estáticas.
              </p>
            </div>

            {showKeys && (
              <>
                <div>
                  <label className={label}>Access Key ID</label>
                  <input
                    className={field}
                    value={v.aws_access_key_id}
                    onChange={(e) => set("aws_access_key_id", e.target.value)}
                    autoComplete="off"
                    placeholder={isEdit && initial?.has_aws_access_key ? "•••••••• (mantém a atual)" : "AKIA…"}
                  />
                </div>
                <div>
                  <label className={label}>Secret Access Key</label>
                  <input
                    type="password"
                    className={field}
                    value={v.aws_secret_access_key}
                    onChange={(e) => set("aws_secret_access_key", e.target.value)}
                    autoComplete="new-password"
                    placeholder={isEdit && initial?.has_aws_secret_key ? "•••••••• (mantém a atual)" : "secret"}
                  />
                </div>
                <div className="sm:col-span-2">
                  <label className={label}>Session Token (opcional — credenciais temporárias)</label>
                  <input
                    type="password"
                    className={field}
                    value={v.aws_session_token}
                    onChange={(e) => set("aws_session_token", e.target.value)}
                    autoComplete="new-password"
                    placeholder={isEdit && initial?.has_aws_session_token ? "•••••••• (mantém o atual)" : "opcional"}
                  />
                </div>
                {isEdit && (initial?.has_aws_access_key || initial?.has_aws_secret_key) && (
                  <p className="sm:col-span-2 -mt-2 text-xs text-gray-400">
                    Deixe os campos em branco para manter as credenciais já cadastradas. As chaves nunca são exibidas.
                  </p>
                )}
              </>
            )}

            {showRole && (
              <>
                <div className="sm:col-span-2">
                  <label className={label}>Role ARN</label>
                  <input className={field} value={v.role_arn} onChange={(e) => set("role_arn", e.target.value)} placeholder="arn:aws:iam::123456789012:role/data-lake" />
                </div>
                <div className="sm:col-span-2">
                  <label className={label}>External ID (opcional)</label>
                  <input className={field} value={v.external_id} onChange={(e) => set("external_id", e.target.value)} placeholder="opcional" />
                </div>
              </>
            )}

            {(v.auth_mode === "instance_profile" || v.auth_mode === "environment") && (
              <p className="sm:col-span-2 rounded-lg bg-blue-50 px-3 py-2 text-xs text-blue-700">
                {v.auth_mode === "instance_profile"
                  ? "As credenciais virão do profile da instância/pod (EC2/EKS). Nenhuma chave é armazenada."
                  : "As credenciais virão das variáveis de ambiente do runtime (AWS_ACCESS_KEY_ID etc.). Nenhuma chave é armazenada."}
              </p>
            )}

            {/* ── Catálogo (Data Lake) ── */}
            <div className="sm:col-span-2 mt-2 border-t border-gray-100 pt-4">
              <span className={sectionTitle}>Catálogo (Data Lake)</span>
            </div>
            <label className="flex items-center gap-2 text-sm text-gray-700 sm:col-span-2">
              <input type="checkbox" className="h-4 w-4 rounded border-gray-300 text-brand-500 focus:ring-brand-500/30" checked={v.catalog_enabled} onChange={(e) => set("catalog_enabled", e.target.checked)} />
              Habilitar catálogo — explorar camadas/tabelas na tela Data Lake
            </label>
            {v.catalog_enabled && (
              <div className="sm:col-span-2">
                <label className={label}>Mapeamento de schema</label>
                <select className={field} value={v.catalog_mode} onChange={(e) => set("catalog_mode", e.target.value)}>
                  <option value="layer_as_schema">Camada = schema (bucket/prefixo desta conexão vira um schema)</option>
                  <option value="prefix_as_schema">Prefixo = schema (1º nível do prefixo vira schema)</option>
                </select>
                <p className="mt-1 text-xs text-gray-400">
                  Bronze/Silver/Gold aparecem como schemas e as pastas como tabelas. Após salvar, use “Atualizar catálogo” na tela Data Lake.
                </p>
              </div>
            )}

            {/* ── Permissões ── */}
            <div className="sm:col-span-2 mt-2 border-t border-gray-100 pt-4">
              <span className={sectionTitle}>Permissões</span>
            </div>
          </>
        )}

        {/* ── Flags comuns ── */}
        {isS3 && (
          <>
            <label className="flex items-center gap-2 text-sm text-gray-700">
              <input type="checkbox" className="h-4 w-4 rounded border-gray-300 text-brand-500 focus:ring-brand-500/30" checked={v.can_read} onChange={(e) => set("can_read", e.target.checked)} />
              Permitir leitura (origem)
            </label>
            <label className="flex items-center gap-2 text-sm text-gray-700">
              <input type="checkbox" className="h-4 w-4 rounded border-gray-300 text-brand-500 focus:ring-brand-500/30" checked={v.can_write} onChange={(e) => set("can_write", e.target.checked)} />
              Permitir escrita (destino)
            </label>
          </>
        )}
        <label className="flex items-center gap-2 text-sm text-gray-700">
          <input type="checkbox" className="h-4 w-4 rounded border-gray-300 text-brand-500 focus:ring-brand-500/30" checked={v.ssl_enabled} onChange={(e) => set("ssl_enabled", e.target.checked)} />
          {isS3 ? "Conexão via SSL/HTTPS" : "SSL habilitado"}
        </label>
        <label className="flex items-center gap-2 text-sm text-gray-700">
          <input type="checkbox" className="h-4 w-4 rounded border-gray-300 text-brand-500 focus:ring-brand-500/30" checked={v.active} onChange={(e) => set("active", e.target.checked)} />
          Conexão ativa
        </label>
      </div>

      {error && <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      {testResult && (
        <div className="mt-4">
          <TestResultView result={testResult} />
        </div>
      )}

      <div className="mt-6 flex items-center justify-end gap-2">
        <SecondaryButton type="button" onClick={onCancel}>
          Cancelar
        </SecondaryButton>
        <SecondaryButton type="button" disabled={!canSubmit || saving} onClick={(e) => submit(e, true)}>
          Salvar e testar
        </SecondaryButton>
        <PrimaryButton type="submit" loading={saving} disabled={!canSubmit}>
          Salvar
        </PrimaryButton>
      </div>
    </form>
  );
}
