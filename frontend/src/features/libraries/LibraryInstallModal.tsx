import { useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Check, PackagePlus } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { Modal, PrimaryButton, SecondaryButton } from "@/components/ui";
import type { LibraryDetail, ValidateResponse } from "@/features/libraries/types";

const inputCls =
  "w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800 outline-none transition-colors focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20";
const labelCls = "mb-1 block text-xs font-medium text-gray-600";

const EXAMPLES = ["pandas", "numpy", "requests", "boto3", "pyarrow", "openpyxl", "sqlalchemy", "psycopg2-binary", "pymysql"];

export function LibraryInstallModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const [advanced, setAdvanced] = useState(false);
  const [pkg, setPkg] = useState("");
  const [version, setVersion] = useState("");
  const [spec, setSpec] = useState("");
  const [scope, setScope] = useState("cluster");
  const [note, setNote] = useState("");
  const [check, setCheck] = useState<ValidateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // The spec that will actually be validated/installed.
  const effectiveSpec = useMemo(() => {
    if (advanced) return spec.trim();
    if (pkg.trim() && version.trim()) {
      return /^(===|==|>=|<=|~=|!=|>|<)/.test(version.trim()) ? `${pkg.trim()}${version.trim()}` : `${pkg.trim()}==${version.trim()}`;
    }
    return pkg.trim();
  }, [advanced, pkg, version, spec]);

  // Debounced live validation via the backend (single source of truth for the rules).
  useEffect(() => {
    if (!open || !effectiveSpec) { setCheck(null); return; }
    const t = setTimeout(async () => {
      try {
        const r = await api.post<ValidateResponse>("/api/v1/libraries/validate-package", { package_spec: effectiveSpec });
        setCheck(r);
      } catch { setCheck(null); }
    }, 350);
    return () => clearTimeout(t);
  }, [effectiveSpec, open]);

  useEffect(() => {
    if (!open) {
      setAdvanced(false); setPkg(""); setVersion(""); setSpec(""); setScope("cluster"); setNote(""); setCheck(null); setError(null);
    }
  }, [open]);

  const install = useMutation({
    mutationFn: () => api.post<LibraryDetail>("/api/v1/libraries/install", {
      package: advanced ? undefined : pkg.trim() || undefined,
      version: advanced ? undefined : version.trim() || undefined,
      package_spec: advanced ? spec.trim() : undefined,
      install_scope: scope,
      note: note.trim() || undefined,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["libraries"] });
      qc.invalidateQueries({ queryKey: ["libraries-summary"] });
      onClose();
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Falha ao solicitar instalação."),
  });

  const canSubmit = !!effectiveSpec && check?.valid !== false;

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Instalar biblioteca"
      description="Informe apenas o nome do pacote e a versão. O comando pip é montado com segurança pelo servidor."
      width="max-w-xl"
      footer={<>
        <SecondaryButton onClick={onClose}>Cancelar</SecondaryButton>
        <PrimaryButton icon={<PackagePlus size={16} />} loading={install.isPending} disabled={!canSubmit} onClick={() => { setError(null); install.mutate(); }}>
          Instalar
        </PrimaryButton>
      </>}
    >
      {error && (
        <div className="mb-4 flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-3.5 py-2 text-sm text-red-700">
          <AlertTriangle size={16} className="mt-0.5 shrink-0" /> {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4">
        <div>
          <label className={labelCls}>Cluster</label>
          <select className={inputCls} disabled value="">
            <option value="">Padrão (worker do T2C Data Ingest)</option>
          </select>
        </div>

        {!advanced ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className={labelCls}>Nome do pacote *</label>
              <input className={inputCls} value={pkg} onChange={(e) => setPkg(e.target.value)} placeholder="pandas" autoFocus />
              <div className="mt-2 flex flex-wrap gap-1">
                {EXAMPLES.map((ex) => (
                  <button key={ex} onClick={() => setPkg(ex)} className="rounded-full border border-gray-200 bg-white px-2 py-0.5 text-[11px] text-gray-500 hover:bg-gray-50">{ex}</button>
                ))}
              </div>
            </div>
            <div>
              <label className={labelCls}>Versão (opcional)</label>
              <input className={inputCls} value={version} onChange={(e) => setVersion(e.target.value)} placeholder="2.2.3" />
            </div>
          </div>
        ) : (
          <div>
            <label className={labelCls}>Especificação completa</label>
            <input className={`${inputCls} font-mono text-xs`} value={spec} onChange={(e) => setSpec(e.target.value)} placeholder="pandas>=2.2.0" autoFocus />
            <p className="mt-1 text-xs text-gray-400">Somente PyPI. URLs, Git e caminhos locais são bloqueados.</p>
          </div>
        )}

        <button onClick={() => setAdvanced((v) => !v)} className="self-start text-xs font-medium text-brand-600 hover:text-brand-700">
          {advanced ? "Usar campos simples" : "Especificação avançada (operadores de versão)"}
        </button>

        <div>
          <label className={labelCls}>Escopo</label>
          <select className={inputCls} value={scope} onChange={(e) => setScope(e.target.value)}>
            <option value="cluster">cluster</option>
            <option value="worker">worker</option>
            <option value="driver">driver</option>
          </select>
        </div>

        <div>
          <label className={labelCls}>Observação (opcional)</label>
          <input className={inputCls} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Motivo / job que precisa" />
        </div>

        {/* Prévia da validação */}
        {effectiveSpec && (
          check?.valid === false ? (
            <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
              <AlertTriangle size={14} className="mt-0.5 shrink-0" /> {check.error}
            </div>
          ) : check?.valid ? (
            <div className="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-700">
              <Check size={14} /> Será instalado: <code className="font-mono">{check.normalized_spec}</code>
            </div>
          ) : (
            <div className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 font-mono text-xs text-gray-500">{effectiveSpec}</div>
          )
        )}
      </div>
    </Modal>
  );
}
