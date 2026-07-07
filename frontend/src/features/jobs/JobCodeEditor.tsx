import { useCallback, useEffect, useMemo, useState } from "react";
import { useBlocker } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import Editor from "@monaco-editor/react";
import {
  AlertTriangle,
  Check,
  Copy,
  FileWarning,
  Lock,
  RefreshCw,
  Save,
  ShieldAlert,
} from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { MONACO_LANGUAGE } from "@/lib/monaco-setup";
import { cn } from "@/lib/cn";
import { EmptyState, PrimaryButton, SecondaryButton } from "@/components/ui";
import { Modal } from "@/components/ui/Modal";
import { Skeleton } from "@/components/ui/LoadingSkeleton";

interface JobCode {
  job_id: number;
  job_name: string;
  script_path: string | null;
  file_name: string | null;
  language: string;
  content: string;
  editable: boolean;
  read_only: boolean;
  last_modified_at: string | null;
  size_bytes: number | null;
}

const LANG_LABEL: Record<string, string> = {
  python: "Python", sql: "SQL", shell: "Shell", yaml: "YAML", json: "JSON", text: "Texto",
};

// Patterns that likely indicate hardcoded credentials in the code.
const CREDENTIAL_RE = /(password\s*=|senha\s*=|secret\s*=|token\s*=|access_key|secret_key)/i;

function fmtBytes(n: number | null): string {
  if (n == null) return "—";
  if (n < 1024) return `${n} B`;
  return `${(n / 1024).toFixed(1)} KB`;
}

export function JobCodeEditor({ jobId }: { jobId: number }) {
  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ["job-code", jobId],
    queryFn: () => api.get<JobCode>(`/api/v1/jobs/${jobId}/code`),
    retry: false,
  });

  const [value, setValue] = useState<string>("");
  const [base, setBase] = useState<string>("");
  const [baseMtime, setBaseMtime] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<{ kind: "ok" | "err"; msg: string } | null>(null);
  const [conflict, setConflict] = useState(false);

  // Seed local state whenever fresh data arrives.
  useEffect(() => {
    if (data) {
      setValue(data.content);
      setBase(data.content);
      setBaseMtime(data.last_modified_at);
    }
  }, [data]);

  const dirty = value !== base;
  const editable = !!data?.editable;
  const hasCredential = useMemo(() => dirty && CREDENTIAL_RE.test(value), [dirty, value]);

  // Guard in-app navigation while there are unsaved changes.
  const blocker = useBlocker(useCallback(() => dirty, [dirty]));

  // Guard browser refresh/close.
  useEffect(() => {
    if (!dirty) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 3500);
    return () => clearTimeout(t);
  }, [toast]);

  async function handleSave() {
    if (!dirty || !editable) return;
    if (hasCredential) {
      const proceed = window.confirm(
        "Detectamos um possível padrão de credencial no código (ex.: password=, secret=, token=).\n\n" +
          "Não salve senhas/tokens no código — use conexões cadastradas ou variáveis seguras.\n\nDeseja salvar mesmo assim?"
      );
      if (!proceed) return;
    }
    setSaving(true);
    setConflict(false);
    try {
      const saved = await api.put<JobCode>(`/api/v1/jobs/${jobId}/code`, {
        content: value,
        expected_last_modified_at: baseMtime,
      });
      setBase(saved.content);
      setValue(saved.content);
      setBaseMtime(saved.last_modified_at);
      setToast({ kind: "ok", msg: "Código salvo com sucesso." });
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setConflict(true);
      } else {
        setToast({ kind: "err", msg: err instanceof Error ? err.message : "Falha ao salvar." });
      }
    } finally {
      setSaving(false);
    }
  }

  async function handleReload() {
    if (dirty && !window.confirm("Descartar alterações não salvas e recarregar o arquivo?")) return;
    setConflict(false);
    const res = await refetch();
    if (res.data) {
      setValue(res.data.content);
      setBase(res.data.content);
      setBaseMtime(res.data.last_modified_at);
    }
  }

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(value);
      setToast({ kind: "ok", msg: "Código copiado." });
    } catch {
      /* ignore */
    }
  }

  if (isLoading) return <Skeleton className="h-[60vh] rounded-2xl" />;

  if (error) {
    const status = error instanceof ApiError ? error.status : 0;
    const msg = error instanceof Error ? error.message : "Não foi possível carregar o código.";
    return (
      <EmptyState
        icon={status === 403 ? <Lock size={24} /> : <FileWarning size={24} />}
        title={status === 403 ? "Sem acesso ao código" : "Código indisponível"}
        description={msg}
      />
    );
  }
  if (!data) return null;

  const monacoLang = MONACO_LANGUAGE[data.language] ?? "plaintext";

  return (
    <div>
      {/* Metadados do arquivo */}
      <div className="mb-3 flex flex-wrap items-center gap-x-6 gap-y-1 text-xs text-gray-500">
        <span>Arquivo: <span className="font-medium text-gray-700">{data.file_name ?? "—"}</span></span>
        <span>Última modificação: {data.last_modified_at ? new Date(data.last_modified_at).toLocaleString("pt-BR") : "—"}</span>
        <span>Tamanho: {fmtBytes(data.size_bytes)}</span>
        <span>Modo: <span className={cn("font-medium", editable ? "text-brand-600" : "text-gray-600")}>{editable ? "Edição" : "Leitura"}</span></span>
      </div>

      {!editable && (
        <div className="mb-3 flex items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 px-3.5 py-2 text-sm text-gray-600">
          <Lock size={15} /> Você possui acesso somente leitura ao código deste job.
        </div>
      )}
      {hasCredential && (
        <div className="mb-3 flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3.5 py-2 text-sm text-amber-800">
          <ShieldAlert size={16} className="mt-0.5 shrink-0" />
          Possível credencial detectada no código. Não salve senhas/tokens aqui — use conexões
          cadastradas ou variáveis seguras.
        </div>
      )}
      {conflict && (
        <div className="mb-3 flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-3.5 py-2 text-sm text-red-700">
          <AlertTriangle size={16} className="mt-0.5 shrink-0" />
          Este arquivo foi alterado por outro usuário ou processo. Recarregue o código antes de salvar.
        </div>
      )}
      {toast && (
        <div
          className={cn(
            "mb-3 flex items-center gap-2 rounded-lg px-3.5 py-2 text-sm",
            toast.kind === "ok" ? "border border-emerald-200 bg-emerald-50 text-emerald-700" : "border border-red-200 bg-red-50 text-red-700"
          )}
        >
          {toast.kind === "ok" ? <Check size={16} /> : <AlertTriangle size={16} />}
          {toast.msg}
        </div>
      )}

      {/* Editor com barra estilo VS Code */}
      <div className="overflow-hidden rounded-2xl border border-graphite-800 bg-graphite-950 shadow-card">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 px-4 py-2.5">
          <div className="flex min-w-0 items-center gap-2 text-sm text-slate-300">
            <span className="font-medium text-slate-100">{data.file_name ?? "código"}</span>
            <span className="truncate font-mono text-xs text-slate-500">{data.script_path ?? "—"}</span>
            {dirty && (
              <span className="inline-flex items-center gap-1 rounded-full bg-brand-500/15 px-2 py-0.5 text-xs font-medium text-brand-300">
                <span className="h-1.5 w-1.5 rounded-full bg-brand-400" /> não salvo
              </span>
            )}
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <span className="rounded-full bg-white/10 px-2 py-0.5 text-xs font-semibold text-slate-300">
              {LANG_LABEL[data.language] ?? data.language}
            </span>
            <button onClick={handleReload} disabled={isFetching} className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium text-slate-300 transition-colors hover:bg-white/10 hover:text-white disabled:opacity-50">
              <RefreshCw size={14} className={isFetching ? "animate-spin" : ""} /> Recarregar
            </button>
            <button onClick={handleCopy} className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium text-slate-300 transition-colors hover:bg-white/10 hover:text-white">
              <Copy size={14} /> Copiar
            </button>
            {editable && (
              <button
                onClick={handleSave}
                disabled={!dirty || saving}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-md px-3 py-1 text-xs font-semibold transition-colors",
                  dirty
                    ? "bg-brand-500 text-white hover:bg-brand-600"
                    : "cursor-not-allowed bg-white/10 text-slate-500"
                )}
              >
                <Save size={14} /> {saving ? "Salvando…" : "Salvar"}
              </button>
            )}
          </div>
        </div>
        <Editor
          height="60vh"
          theme="vs-dark"
          language={monacoLang}
          value={value}
          onChange={(v) => setValue(v ?? "")}
          options={{
            readOnly: !editable,
            fontSize: 13,
            fontFamily: "JetBrains Mono, ui-monospace, monospace",
            minimap: { enabled: true },
            scrollBeyondLastLine: false,
            lineNumbers: "on",
            renderWhitespace: "selection",
            automaticLayout: true,
            tabSize: 4,
          }}
          loading={<div className="p-6 text-sm text-slate-400">Carregando editor…</div>}
        />
      </div>

      {/* Confirmação ao sair com alterações não salvas */}
      <Modal
        open={blocker.state === "blocked"}
        onClose={() => blocker.reset?.()}
        title="Alterações não salvas"
        footer={
          <>
            <SecondaryButton onClick={() => blocker.reset?.()}>Continuar editando</SecondaryButton>
            <PrimaryButton className="bg-red-600 hover:bg-red-700" onClick={() => blocker.proceed?.()}>
              Sair sem salvar
            </PrimaryButton>
          </>
        }
      >
        <p className="text-sm text-gray-600">
          Existem alterações não salvas. Deseja sair mesmo assim?
        </p>
      </Modal>
    </div>
  );
}
