import { useMemo, useState } from "react";
import type { FormEvent } from "react";

import { PrimaryButton, SecondaryButton } from "@/components/ui";
import { ConnectionTestResult as TestResultView } from "@/features/connections/ConnectionTestResult";
import type { ConnectionSubmitPayload } from "@/features/connections/ConnectionForm";
import type {
  Connection, ConnectionTestResult, ConnectorField, ConnectorMeta,
} from "@/features/connections/types";

const label = "block text-sm font-medium text-gray-700";
const fieldCls =
  "mt-1.5 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-500/20";
const sectionTitle = "text-xs font-semibold uppercase tracking-wide text-gray-400";

type Values = Record<string, string | boolean | number>;

function initialValues(meta: ConnectorMeta, initial: Connection | null): Values {
  const ep = (initial?.extra_params ?? {}) as Record<string, unknown>;
  const v: Values = { name: initial?.name ?? "", description: initial?.description ?? "" };
  for (const f of meta.fields) {
    if (f.secret) { v[f.name] = ""; continue; } // secrets nunca pré-preenchidos
    let cur: unknown;
    if (f.store.startsWith("col:")) {
      const attr = f.store.slice(4) as keyof Connection;
      cur = initial ? (initial as unknown as Record<string, unknown>)[attr] : undefined;
    } else if (f.store === "extra") {
      cur = ep[f.name];
    }
    if (cur == null) cur = f.default ?? (f.kind === "checkbox" ? false : "");
    v[f.name] = cur as string | boolean | number;
  }
  return v;
}

/** Formulário genérico dirigido pelo registry (/connections/types) — cobre todos os tipos
 *  exceto S3 (que tem formulário dedicado). Nada de campos hardcoded. */
export function DynamicConnectionForm({
  meta, initial, saving, testResult, onSubmit, onCancel,
}: {
  meta: ConnectorMeta;
  initial: Connection | null;
  saving?: boolean;
  testResult?: ConnectionTestResult | null;
  onSubmit: (payload: ConnectionSubmitPayload, testAfter: boolean) => void;
  onCancel: () => void;
}) {
  const [v, setV] = useState<Values>(() => initialValues(meta, initial));
  const [error, setError] = useState<string | null>(null);
  const isEdit = !!initial;

  function set(name: string, value: string | boolean | number) {
    setV((prev) => ({ ...prev, [name]: value }));
  }

  const visibleFields = useMemo(
    () => meta.fields.filter((f) => !f.show_if || f.show_if.in.includes(String(v[f.show_if.field] ?? ""))),
    [meta.fields, v]
  );

  // Agrupa por seção preservando a ordem de aparição.
  const sections = useMemo(() => {
    const order: string[] = [];
    const map: Record<string, ConnectorField[]> = {};
    for (const f of visibleFields) {
      if (!map[f.section]) { map[f.section] = []; order.push(f.section); }
      map[f.section].push(f);
    }
    return order.map((s) => ({ section: s, fields: map[s] }));
  }, [visibleFields]);

  function secretPlaceholder(f: ConnectorField): string {
    const has = f.name === "password"
      ? initial?.has_password
      : (initial?.secrets_present ?? []).includes(f.name);
    return isEdit && has ? "•••••••• (mantém o atual)" : f.placeholder;
  }

  function build(): ConnectionSubmitPayload | null {
    const name = String(v.name ?? "").trim();
    if (!name) { setError("Nome é obrigatório."); return null; }
    const payload: ConnectionSubmitPayload = {
      name, description: String(v.description ?? "").trim() || null,
      connection_type: meta.type, host: null, port: null, database_name: null,
      username: null, schema_name: null, ssl_enabled: false, active: true,
      can_read: true, can_write: false, extra_params: {},
    };
    const extra: Record<string, unknown> = {};
    const secrets: Record<string, string> = {};
    for (const f of visibleFields) {
      const raw = v[f.name];
      if (f.required && f.kind !== "checkbox" && !String(raw ?? "").trim() && !f.secret) {
        setError(`Campo obrigatório: ${f.label}`); return null;
      }
      if (f.store === "password") {
        if (raw) payload.password = String(raw);
      } else if (f.store === "secret") {
        if (raw) secrets[f.name] = String(raw);
      } else if (f.store === "extra") {
        if (raw !== "" && raw != null) extra[f.name] = f.kind === "number" ? Number(raw) : raw;
      } else if (f.store.startsWith("col:")) {
        const attr = f.store.slice(4);
        const val = f.kind === "number" ? (raw === "" ? null : Number(raw)) : (f.kind === "checkbox" ? !!raw : (String(raw).trim() || null));
        (payload as unknown as Record<string, unknown>)[attr] = val;
      }
    }
    payload.extra_params = Object.keys(extra).length ? extra : null;
    if (Object.keys(secrets).length) payload.secrets = secrets;
    return payload;
  }

  function submit(e: FormEvent, testAfter: boolean) {
    e.preventDefault();
    setError(null);
    const p = build();
    if (p) onSubmit(p, testAfter);
  }

  return (
    <form onSubmit={(e) => submit(e, false)}>
      <div className="space-y-4">
        {/* Identificação */}
        <div>
          <span className={sectionTitle}>Identificação</span>
          <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <label className={label}>Nome da conexão *</label>
              <input className={fieldCls} value={String(v.name ?? "")} onChange={(e) => set("name", e.target.value)} required />
            </div>
            <div className="sm:col-span-2">
              <label className={label}>Descrição</label>
              <input className={fieldCls} value={String(v.description ?? "")} onChange={(e) => set("description", e.target.value)} />
            </div>
          </div>
        </div>

        {sections.map(({ section, fields }) => (
          <div key={section} className="border-t border-gray-100 pt-3">
            <span className={sectionTitle}>{section}</span>
            <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-2">
              {fields.map((f) => (
                <div key={f.name} className={f.kind === "textarea" || f.kind === "checkbox" ? "sm:col-span-2" : ""}>
                  {f.kind === "checkbox" ? (
                    <label className="flex items-center gap-2 text-sm text-gray-700">
                      <input type="checkbox" className="h-4 w-4 rounded border-gray-300 text-brand-500 focus:ring-brand-500/30"
                        checked={!!v[f.name]} onChange={(e) => set(f.name, e.target.checked)} />
                      {f.label}
                    </label>
                  ) : (
                    <>
                      <label className={label}>{f.label}{f.required ? " *" : ""}</label>
                      {f.kind === "select" ? (
                        <select className={fieldCls} value={String(v[f.name] ?? "")} onChange={(e) => set(f.name, e.target.value)}>
                          {f.options.map((o) => <option key={o} value={o}>{o}</option>)}
                        </select>
                      ) : f.kind === "textarea" ? (
                        <textarea className={`${fieldCls} h-20 font-mono text-xs`} value={String(v[f.name] ?? "")}
                          onChange={(e) => set(f.name, e.target.value)} placeholder={f.placeholder} />
                      ) : (
                        <input
                          type={f.kind === "password" ? "password" : f.kind === "number" ? "number" : "text"}
                          className={fieldCls}
                          value={String(v[f.name] ?? "")}
                          onChange={(e) => set(f.name, f.kind === "number" ? (e.target.value === "" ? "" : Number(e.target.value)) : e.target.value)}
                          autoComplete={f.secret ? "new-password" : "off"}
                          placeholder={f.secret ? secretPlaceholder(f) : f.placeholder}
                        />
                      )}
                      {f.help && <p className="mt-1 text-xs text-gray-400">{f.help}</p>}
                    </>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {error && <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      {testResult && <div className="mt-4"><TestResultView result={testResult} /></div>}

      <div className="mt-6 flex items-center justify-end gap-2">
        <SecondaryButton type="button" onClick={onCancel}>Cancelar</SecondaryButton>
        <SecondaryButton type="button" disabled={saving} onClick={(e) => submit(e, true)}>Salvar e testar</SecondaryButton>
        <PrimaryButton type="submit" loading={saving}>Salvar</PrimaryButton>
      </div>
    </form>
  );
}
