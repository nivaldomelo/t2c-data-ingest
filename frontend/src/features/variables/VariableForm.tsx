import { useState } from "react";
import type { FormEvent } from "react";
import { ShieldAlert } from "lucide-react";

import { PrimaryButton, SecondaryButton } from "@/components/ui";
import type { Variable } from "@/features/variables/types";
import { ENVIRONMENTS, VARIABLE_SCOPES, VARIABLE_TYPES, normalizeName } from "@/features/variables/types";

export interface VariablePayload {
  name: string;
  description: string | null;
  value?: string | null;
  variable_type: string;
  scope: string;
  environment: string | null;
  is_secret: boolean;
  active: boolean;
}

const label = "block text-sm font-medium text-gray-700";
const hint = "mt-1 text-xs text-gray-400";
const field =
  "mt-1.5 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-500/20";

export function VariableForm({
  initial,
  saving,
  onSubmit,
  onCancel,
}: {
  initial: Variable | null;
  saving?: boolean;
  onSubmit: (p: VariablePayload) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [type, setType] = useState(initial?.variable_type ?? "string");
  const [value, setValue] = useState(initial?.is_secret ? "" : initial?.value ?? "");
  const [scope, setScope] = useState(initial?.scope ?? "global");
  const [environment, setEnvironment] = useState(initial?.environment ?? "");
  const [isSecret, setIsSecret] = useState(initial?.is_secret ?? false);
  const [active, setActive] = useState(initial?.active ?? true);
  const [error, setError] = useState<string | null>(null);

  const effectiveSecret = isSecret || type === "secret";

  function validateValue(): string | null {
    if (!value.trim()) return null;
    if (type === "json") {
      try { JSON.parse(value); } catch { return "Valor não é um JSON válido."; }
    }
    if (type === "integer" && !/^-?\d+$/.test(value.trim())) return "Valor deve ser um inteiro.";
    if (type === "decimal" && !/^-?\d+(\.\d+)?$/.test(value.trim())) return "Valor deve ser um decimal.";
    if (type === "boolean" && !["true", "false"].includes(value.trim().toLowerCase())) return "Valor booleano deve ser true ou false.";
    return null;
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    const nm = normalizeName(name);
    if (!nm) return setError("Nome da variável é obrigatório.");
    const ve = validateValue();
    if (ve) return setError(ve);
    const payload: VariablePayload = {
      name: nm,
      description: description.trim() || null,
      variable_type: type,
      scope,
      environment: environment || null,
      is_secret: effectiveSecret,
      active,
    };
    // Empty value on a secret keeps the current one (omit field).
    if (!(effectiveSecret && initial && !value)) {
      payload.value = value.trim() === "" ? null : value;
    }
    onSubmit(payload);
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <label className={label}>Nome da variável *</label>
          <input
            className={`${field} font-mono`}
            value={name}
            onChange={(e) => setName(e.target.value)}
            onBlur={() => setName((n) => normalizeName(n))}
            placeholder="DATA_EXECUCAO"
          />
          <p className={hint}>Formato seguro para código: MAIÚSCULAS_COM_UNDERLINE (auto-formatado).</p>
        </div>
        <div>
          <label className={label}>Tipo *</label>
          <select className={field} value={type} onChange={(e) => setType(e.target.value)}>
            {VARIABLE_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
        <div className="sm:col-span-2">
          <label className={label}>Descrição</label>
          <input className={field} value={description} onChange={(e) => setDescription(e.target.value)} />
        </div>

        <div className="sm:col-span-2">
          <label className={label}>Valor {effectiveSecret && <span className="text-amber-600">(secreto)</span>}</label>
          {type === "json" ? (
            <textarea className={`${field} h-20 font-mono text-xs`} value={value} onChange={(e) => setValue(e.target.value)} placeholder='{"chave": "valor"}' />
          ) : (
            <input
              className={`${field} ${effectiveSecret ? "font-mono" : ""}`}
              type={effectiveSecret ? "password" : "text"}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder={effectiveSecret && initial?.has_value ? "•••••••• (mantém o atual)" : type === "boolean" ? "true / false" : "valor"}
              autoComplete="off"
            />
          )}
          {effectiveSecret && initial?.has_value && <p className={hint}>Deixe em branco para manter o valor atual.</p>}
        </div>

        <div>
          <label className={label}>Escopo *</label>
          <select className={field} value={scope} onChange={(e) => setScope(e.target.value)}>
            {VARIABLE_SCOPES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div>
          <label className={label}>Ambiente</label>
          <select className={field} value={environment} onChange={(e) => setEnvironment(e.target.value)}>
            <option value="">— (global, sem ambiente)</option>
            {ENVIRONMENTS.map((e) => <option key={e} value={e}>{e}</option>)}
          </select>
        </div>

        <label className="flex items-center gap-2 text-sm text-gray-700">
          <input type="checkbox" className="h-4 w-4 rounded border-gray-300 text-brand-500 focus:ring-brand-500/30" checked={effectiveSecret} disabled={type === "secret"} onChange={(e) => setIsSecret(e.target.checked)} />
          Secreta
        </label>
        <label className="flex items-center gap-2 text-sm text-gray-700">
          <input type="checkbox" className="h-4 w-4 rounded border-gray-300 text-brand-500 focus:ring-brand-500/30" checked={active} onChange={(e) => setActive(e.target.checked)} />
          Ativa
        </label>
      </div>

      {effectiveSecret && (
        <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3.5 py-2 text-xs text-amber-800">
          <ShieldAlert size={15} className="mt-0.5 shrink-0" />
          Para credenciais de banco de dados, prefira a tela <b>Conexões</b>. Use variáveis
          secretas apenas para segredos de parâmetros de execução. O valor é criptografado e
          nunca é exibido depois de salvo.
        </div>
      )}

      {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

      <div className="flex items-center justify-end gap-2 border-t border-gray-100 pt-4">
        <SecondaryButton type="button" onClick={onCancel}>Cancelar</SecondaryButton>
        <PrimaryButton type="submit" loading={saving}>Salvar</PrimaryButton>
      </div>
    </form>
  );
}
