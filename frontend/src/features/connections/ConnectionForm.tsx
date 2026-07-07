import { useMemo, useState } from "react";
import type { FormEvent } from "react";

import { PrimaryButton, SecondaryButton } from "@/components/ui";
import { ConnectionTestResult as TestResultView } from "@/features/connections/ConnectionTestResult";
import type {
  Connection,
  ConnectionFormValues,
  ConnectionTestResult,
  ConnectionType,
} from "@/features/connections/types";
import { DEFAULT_PORTS } from "@/features/connections/types";

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
  extra_params: Record<string, unknown> | null;
}

function toValues(c: Connection | null): ConnectionFormValues {
  return {
    name: c?.name ?? "",
    description: c?.description ?? "",
    connection_type: c?.connection_type ?? "postgres",
    host: c?.host ?? "",
    port: c?.port ?? DEFAULT_PORTS[c?.connection_type ?? "postgres"],
    database_name: c?.database_name ?? "",
    username: c?.username ?? "",
    password: "",
    schema_name: c?.schema_name ?? "",
    ssl_enabled: c?.ssl_enabled ?? false,
    active: c?.active ?? true,
    extra_params: c?.extra_params ? JSON.stringify(c.extra_params, null, 2) : "",
  };
}

const label = "block text-sm font-medium text-gray-700";
const field =
  "mt-1.5 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-500/20";

export function ConnectionForm({
  initial,
  saving,
  testResult,
  onSubmit,
  onCancel,
}: {
  initial: Connection | null;
  saving?: boolean;
  testResult?: ConnectionTestResult | null;
  onSubmit: (payload: ConnectionSubmitPayload, testAfter: boolean) => void;
  onCancel: () => void;
}) {
  const [v, setV] = useState<ConnectionFormValues>(() => toValues(initial));
  const [error, setError] = useState<string | null>(null);
  const isEdit = !!initial;

  function set<K extends keyof ConnectionFormValues>(key: K, value: ConnectionFormValues[K]) {
    setV((prev) => ({ ...prev, [key]: value }));
  }

  function changeType(type: ConnectionType) {
    setV((prev) => ({
      ...prev,
      connection_type: type,
      // Sugere a porta padrão quando vazia ou igual à porta padrão do tipo anterior.
      port:
        prev.port === "" || prev.port === DEFAULT_PORTS[prev.connection_type]
          ? DEFAULT_PORTS[type]
          : prev.port,
    }));
  }

  const canSubmit = useMemo(() => v.name.trim().length > 0, [v.name]);

  function build(): ConnectionSubmitPayload | null {
    let extra: Record<string, unknown> | null = null;
    if (v.extra_params.trim()) {
      try {
        extra = JSON.parse(v.extra_params);
      } catch {
        setError("Parâmetros extras devem ser um JSON válido.");
        return null;
      }
    }
    const payload: ConnectionSubmitPayload = {
      name: v.name.trim(),
      description: v.description.trim() || null,
      connection_type: v.connection_type,
      host: v.host.trim() || null,
      port: v.port === "" ? null : Number(v.port),
      database_name: v.database_name.trim() || null,
      username: v.username.trim() || null,
      schema_name: v.schema_name.trim() || null,
      ssl_enabled: v.ssl_enabled,
      active: v.active,
      extra_params: extra,
    };
    // Senha vazia mantém a atual (backend só sobrescreve quando vem preenchida).
    if (v.password) payload.password = v.password;
    return payload;
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
        <div className="sm:col-span-2">
          <label className={label}>Nome da conexão *</label>
          <input className={field} value={v.name} onChange={(e) => set("name", e.target.value)} placeholder="ex.: bd_clientes_prod" required />
        </div>

        <div className="sm:col-span-2">
          <label className={label}>Descrição</label>
          <input className={field} value={v.description} onChange={(e) => set("description", e.target.value)} placeholder="Para que serve esta conexão" />
        </div>

        <div>
          <label className={label}>Tipo *</label>
          <select className={field} value={v.connection_type} onChange={(e) => changeType(e.target.value as ConnectionType)}>
            <option value="postgres">PostgreSQL</option>
            <option value="mysql">MySQL</option>
          </select>
        </div>
        <div>
          <label className={label}>Porta</label>
          <input
            type="number"
            className={field}
            value={v.port}
            onChange={(e) => set("port", e.target.value === "" ? "" : Number(e.target.value))}
            placeholder={String(DEFAULT_PORTS[v.connection_type])}
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

        <label className="flex items-center gap-2 text-sm text-gray-700">
          <input type="checkbox" className="h-4 w-4 rounded border-gray-300 text-brand-500 focus:ring-brand-500/30" checked={v.ssl_enabled} onChange={(e) => set("ssl_enabled", e.target.checked)} />
          SSL habilitado
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
