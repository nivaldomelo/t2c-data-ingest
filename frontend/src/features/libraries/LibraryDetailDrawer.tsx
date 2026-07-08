import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Copy, RefreshCw, Trash2, X } from "lucide-react";

import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { LibraryStatusBadge } from "@/features/libraries/LibraryStatusBadge";
import { ACTION_LABEL, type LibraryDetail } from "@/features/libraries/types";

type Tab = "resumo" | "historico" | "logs" | "uso";
const TABS: { key: Tab; label: string }[] = [
  { key: "resumo", label: "Resumo" },
  { key: "historico", label: "Histórico" },
  { key: "logs", label: "Logs" },
  { key: "uso", label: "Como usar" },
];

function fmt(t: string | null): string {
  return t ? new Date(t).toLocaleString("pt-BR") : "—";
}

export function LibraryDetailDrawer({
  libraryId, open, onClose, canInstall, canUninstall,
}: {
  libraryId: number | null; open: boolean; onClose: () => void; canInstall: boolean; canUninstall: boolean;
}) {
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("resumo");

  useEffect(() => { if (open) setTab("resumo"); }, [open, libraryId]);

  const { data } = useQuery({
    queryKey: ["library", libraryId],
    queryFn: () => api.get<LibraryDetail>(`/api/v1/libraries/${libraryId}`),
    enabled: open && libraryId != null,
    refetchInterval: (q) => {
      const d = q.state.data as LibraryDetail | undefined;
      return d && ["queued", "installing"].includes(d.status) ? 3000 : false;
    },
  });

  const lastActionId = data?.actions?.[0]?.id;
  const { data: logs } = useQuery({
    queryKey: ["library-action-logs", lastActionId],
    queryFn: () => api.get<{ logs: string; command_safe: string | null }>(`/api/v1/library-actions/${lastActionId}/logs`),
    enabled: open && tab === "logs" && lastActionId != null,
  });

  const reinstall = useMutation({
    mutationFn: () => api.post(`/api/v1/libraries/${libraryId}/reinstall`, {}),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["library", libraryId] }); qc.invalidateQueries({ queryKey: ["libraries"] }); },
  });
  const uninstall = useMutation({
    mutationFn: () => api.post(`/api/v1/libraries/${libraryId}/uninstall`, {}),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["library", libraryId] }); qc.invalidateQueries({ queryKey: ["libraries"] }); },
  });

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="fixed inset-0 bg-graphite-950/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative z-10 flex h-full w-full max-w-2xl flex-col bg-slate-50 shadow-card-hover">
        {/* header */}
        <div className="flex items-start justify-between gap-3 border-b border-gray-200 bg-white px-6 py-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h2 className="truncate text-lg font-bold text-gray-900">{data?.package_name ?? "Biblioteca"}</h2>
              {data && <LibraryStatusBadge status={data.status} />}
            </div>
            <p className="mt-0.5 font-mono text-xs text-gray-400">{data?.package_spec}</p>
          </div>
          <button onClick={onClose} className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-700"><X size={18} /></button>
        </div>

        {/* actions */}
        {data && (
          <div className="flex gap-2 border-b border-gray-200 bg-white px-6 py-2.5">
            {canInstall && (
              <button onClick={() => reinstall.mutate()} disabled={reinstall.isPending || ["queued", "installing"].includes(data.status)}
                className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50">
                <RefreshCw size={13} /> Reinstalar
              </button>
            )}
            {canUninstall && data.status !== "removed" && (
              <button onClick={() => uninstall.mutate()} disabled={uninstall.isPending || ["queued", "installing"].includes(data.status)}
                className="inline-flex items-center gap-1.5 rounded-lg border border-red-200 bg-white px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50 disabled:opacity-50">
                <Trash2 size={13} /> Remover
              </button>
            )}
          </div>
        )}

        {/* tabs */}
        <div className="border-b border-gray-200 bg-white px-6">
          <nav className="-mb-px flex gap-1">
            {TABS.map((t) => (
              <button key={t.key} onClick={() => setTab(t.key)}
                className={cn("border-b-2 px-3 py-2.5 text-sm font-medium transition-colors",
                  tab === t.key ? "border-brand-500 text-brand-600" : "border-transparent text-gray-500 hover:text-gray-700")}>
                {t.label}
              </button>
            ))}
          </nav>
        </div>

        {/* body */}
        <div className="min-h-0 flex-1 overflow-auto p-6">
          {!data ? (
            <p className="text-sm text-gray-400">Carregando…</p>
          ) : tab === "resumo" ? (
            <dl className="grid grid-cols-2 gap-x-6 gap-y-4 rounded-2xl border border-gray-200 bg-white p-5">
              <Field label="Pacote">{data.package_name}</Field>
              <Field label="Versão">{data.package_version ?? "—"}</Field>
              <Field label="Status"><LibraryStatusBadge status={data.status} /></Field>
              <Field label="Origem">{data.source}</Field>
              <Field label="Escopo">{data.install_scope}</Field>
              <Field label="Cluster">{data.cluster_id ?? "Padrão (worker)"}</Field>
              <Field label="Instalado em">{fmt(data.installed_at)}</Field>
              <Field label="Instalado por">{data.installed_by ?? "—"}</Field>
              <Field label="Última ação">{fmt(data.last_action_at)}{data.last_action_status ? ` · ${data.last_action_status}` : ""}</Field>
              {data.note && <div className="col-span-2"><Field label="Observação">{data.note}</Field></div>}
              {data.last_action_message && data.status === "failed" && (
                <div className="col-span-2 rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700">{data.last_action_message}</div>
              )}
            </dl>
          ) : tab === "historico" ? (
            <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white">
              {data.actions.length === 0 ? (
                <p className="p-5 text-sm text-gray-400">Sem histórico de ações.</p>
              ) : data.actions.map((a) => (
                <div key={a.id} className="flex items-center justify-between gap-3 border-b border-gray-100 px-5 py-3 last:border-0">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-gray-800">{ACTION_LABEL[a.action] ?? a.action}</p>
                    <p className="font-mono text-xs text-gray-400">{a.package_spec}</p>
                  </div>
                  <div className="shrink-0 text-right">
                    <LibraryStatusBadge status={a.status === "success" ? "installed" : a.status === "failed" ? "failed" : "queued"} />
                    <p className="mt-1 text-xs text-gray-400">{fmt(a.finished_at ?? a.created_at)}{a.duration_seconds != null ? ` · ${a.duration_seconds}s` : ""}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : tab === "logs" ? (
            <div className="overflow-hidden rounded-2xl border border-graphite-800 bg-graphite-950">
              {logs?.command_safe && <div className="border-b border-white/10 px-4 py-2 font-mono text-xs text-brand-300">$ {logs.command_safe}</div>}
              <pre className="scrollbar-dark max-h-[60vh] overflow-auto p-4 font-mono text-xs leading-relaxed text-slate-200 whitespace-pre-wrap break-words">
{logs?.logs || "Sem logs disponíveis."}
              </pre>
            </div>
          ) : (
            <UsageTab pkg={data.package_name} />
          )}
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-gray-400">{label}</dt>
      <dd className="mt-0.5 text-sm text-gray-800">{children}</dd>
    </div>
  );
}

function CodeBlock({ code }: { code: string }) {
  const [done, setDone] = useState(false);
  return (
    <div className="relative overflow-hidden rounded-xl border border-graphite-800 bg-graphite-950">
      <button onClick={async () => { try { await navigator.clipboard.writeText(code); setDone(true); setTimeout(() => setDone(false), 1500); } catch { /* */ } }}
        className="absolute right-2 top-2 inline-flex items-center gap-1 rounded-md bg-white/10 px-2 py-1 text-[11px] font-medium text-slate-300 hover:bg-white/20">
        {done ? <Check size={12} /> : <Copy size={12} />} {done ? "Copiado" : "Copiar"}
      </button>
      <pre className="overflow-x-auto p-4 font-mono text-xs leading-relaxed text-slate-200">{code}</pre>
    </div>
  );
}

function UsageTab({ pkg }: { pkg: string }) {
  const py = `import ${pkg.replace(/-/g, "_")}\n\n# Use a biblioteca normalmente no seu job Python\nprint(${pkg.replace(/-/g, "_")}.__name__)`;
  const spark = `from pyspark.sql import SparkSession\n\nspark = (\n    SparkSession.builder\n    .appName("job_com_biblioteca")\n    .getOrCreate()\n)\n\n# A biblioteca precisa estar disponível no Python usado pelo driver e pelos executors\nimport ${pkg.replace(/-/g, "_")}\nprint("ok")`;
  return (
    <div className="space-y-5">
      <div>
        <h3 className="mb-2 text-sm font-semibold text-gray-900">Em um job Python</h3>
        <CodeBlock code={py} />
      </div>
      <div>
        <h3 className="mb-2 text-sm font-semibold text-gray-900">Em um job Spark</h3>
        <CodeBlock code={spark} />
      </div>
      <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3.5 py-2.5 text-sm text-amber-800">
        <span>⚠️</span>
        <p>A biblioteca precisa estar disponível no ambiente Python usado pelo <b>driver</b> e pelos <b>executors</b> Spark.
          Nesta versão a instalação ocorre no worker do T2C Data Ingest (driver/spark-submit). Para libs usadas nos
          executors, pode ser necessário recriar as imagens dos workers Spark.</p>
      </div>
    </div>
  );
}
