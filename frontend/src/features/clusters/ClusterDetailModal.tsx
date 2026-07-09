import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Cpu, RefreshCw, Server, XCircle } from "lucide-react";

import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useAuth } from "@/lib/auth";
import {
  CLUSTER_STATUS, WORKER_STATUS, fmtDate,
  type Cluster, type ClusterValidation, type ClusterWorkers,
} from "@/features/clusters/types";

type Tab = "resumo" | "workers" | "bibliotecas" | "validacoes" | "config";
const TABS: { key: Tab; label: string }[] = [
  { key: "resumo", label: "Resumo" },
  { key: "workers", label: "Workers" },
  { key: "bibliotecas", label: "Bibliotecas" },
  { key: "validacoes", label: "Validações" },
  { key: "config", label: "Configurações" },
];

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-gray-400">{label}</dt>
      <dd className="mt-0.5 text-sm text-gray-800">{children}</dd>
    </div>
  );
}

export function ClusterDetailModal({ cluster, open, onClose }: { cluster: Cluster; open: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const { can } = useAuth();
  const [tab, setTab] = useState<Tab>("resumo");
  const canValidate = can("ingest:clusters:validate");
  const st = CLUSTER_STATUS[cluster.status] ?? CLUSTER_STATUS.inactive;

  const { data: workers } = useQuery({
    queryKey: ["cluster-workers", cluster.id],
    queryFn: () => api.get<ClusterWorkers>(`/api/v1/clusters/${cluster.id}/workers`),
    enabled: open,
    refetchInterval: open && tab === "workers" ? 5000 : false,
  });
  const { data: validations } = useQuery({
    queryKey: ["cluster-validations", cluster.id],
    queryFn: () => api.get<ClusterValidation[]>(`/api/v1/clusters/${cluster.id}/validations`),
    enabled: open,
    refetchInterval: (q) => ((q.state.data as ClusterValidation[] | undefined)?.some((v) => ["queued", "running"].includes(v.status)) ? 3000 : false),
  });
  const { data: libs } = useQuery({
    queryKey: ["runtime-libraries"],
    queryFn: () => api.get<{ package_name: string; package_version: string | null; active: boolean }[]>("/api/v1/runtime/libraries"),
    enabled: open && tab === "bibliotecas",
  });

  const validate = useMutation({
    mutationFn: (kind: "libraries" | "distributed-execution") => api.post(`/api/v1/clusters/${cluster.id}/${kind === "libraries" ? "validate-libraries" : "validate-distributed-execution"}`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["cluster-validations", cluster.id] }),
  });

  if (!open) return null;
  const detected = workers?.workers_detected ?? cluster.worker_count ?? 0;
  const expected = workers?.workers_expected ?? cluster.expected_workers ?? 3;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto p-4 sm:p-6">
      <div className="fixed inset-0 bg-graphite-950/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative z-10 my-8 w-full max-w-3xl rounded-2xl border border-gray-200 bg-white shadow-card-hover">
        <div className="flex items-start justify-between border-b border-gray-100 px-6 py-4">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-bold text-gray-900">{cluster.name}</h2>
              <span className={cn("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium", st.tone)}>
                <span className={cn("h-1.5 w-1.5 rounded-full", st.dot)} /> {st.label}
              </span>
            </div>
            <p className="mt-0.5 font-mono text-xs text-gray-400">{cluster.spark_master_url}</p>
          </div>
          <button onClick={onClose} className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-700"><XCircle size={18} /></button>
        </div>

        <div className="border-b border-gray-100 px-6">
          <nav className="-mb-px flex gap-1 overflow-x-auto">
            {TABS.map((t) => (
              <button key={t.key} onClick={() => setTab(t.key)}
                className={cn("shrink-0 border-b-2 px-3 py-2.5 text-sm font-medium transition-colors",
                  tab === t.key ? "border-brand-500 text-brand-600" : "border-transparent text-gray-500 hover:text-gray-700")}>
                {t.label}
              </button>
            ))}
          </nav>
        </div>

        <div className="max-h-[65vh] overflow-auto p-6">
          {tab === "resumo" && (
            <dl className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3">
              <Field label="Tipo">{cluster.type}</Field>
              <Field label="Ambiente">{cluster.environment_label ?? "—"}</Field>
              <Field label="Status">{st.label}</Field>
              <Field label="Workers">{cluster.worker_count ?? "—"}</Field>
              <Field label="Cores totais">{cluster.total_cores ?? "—"}</Field>
              <Field label="Memória total">{cluster.total_memory ?? "—"}</Field>
              <Field label="Runtime">{cluster.runtime_image ? <span className="font-mono text-xs">{cluster.runtime_image}</span> : "Não informado"}</Field>
              <Field label="Última verificação">{fmtDate(cluster.last_checked_at)}</Field>
              <Field label="Última validação">{cluster.last_validation_status ?? "Não validado"}</Field>
              <div className="col-span-full"><Field label="Master URL"><span className="break-all font-mono text-xs">{cluster.spark_master_url}</span></Field></div>
            </dl>
          )}

          {tab === "workers" && (
            <div className="space-y-3">
              <div className={cn("flex items-start gap-2 rounded-lg border px-3.5 py-2.5 text-sm",
                detected >= expected ? "border-emerald-200 bg-emerald-50 text-emerald-800" : "border-amber-200 bg-amber-50 text-amber-800")}>
                {detected >= expected ? <CheckCircle2 size={16} className="mt-0.5 shrink-0" /> : <AlertTriangle size={16} className="mt-0.5 shrink-0" />}
                {detected >= expected
                  ? `Cluster pronto para validação distribuída com ${detected} workers ativos.`
                  : `Atenção: ${detected} worker(s) ativo(s). Para validar execução distribuída local, configure pelo menos ${expected} workers Spark.`}
              </div>
              {(workers?.workers ?? []).length === 0 ? (
                <div className="rounded-lg border border-gray-200 bg-gray-50 px-4 py-6 text-center text-sm text-gray-500">
                  Nenhum worker detectado. Verifique se os containers Spark workers estão ativos e conectados ao master.
                </div>
              ) : (
                <div className="overflow-hidden rounded-xl border border-gray-100">
                  {(workers?.workers ?? []).map((w) => {
                    const ws = WORKER_STATUS[w.status] ?? WORKER_STATUS.inactive;
                    return (
                      <div key={w.name} className="flex items-center justify-between gap-3 border-b border-gray-50 px-4 py-2.5 last:border-0">
                        <div className="flex items-center gap-2">
                          <Server size={15} className="text-gray-400" />
                          <div>
                            <p className="font-mono text-sm text-gray-800">{w.name}</p>
                            <p className="font-mono text-xs text-gray-400">{w.host}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-4 text-xs text-gray-500">
                          <span>{w.cores ?? "—"} cores · {w.memory ?? "—"}</span>
                          <span className={cn("inline-flex items-center gap-1.5 font-medium", ws.tone)}>
                            <span className={cn("h-1.5 w-1.5 rounded-full", ws.dot)} /> {ws.label}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
              {canValidate && (
                <button onClick={() => validate.mutate("distributed-execution")} disabled={validate.isPending}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-brand-500 px-3 py-1.5 text-sm font-semibold text-white hover:bg-brand-600 disabled:opacity-50">
                  <Cpu size={15} /> Validar execução distribuída
                </button>
              )}
            </div>
          )}

          {tab === "bibliotecas" && (
            <div className="space-y-3">
              {(libs ?? []).length === 0 ? (
                <p className="text-sm text-gray-400">Nenhuma biblioteca cadastrada no runtime do cluster.</p>
              ) : (
                <div className="overflow-hidden rounded-xl border border-gray-100">
                  {(libs ?? []).map((l) => (
                    <div key={l.package_name} className="flex items-center justify-between border-b border-gray-50 px-4 py-2 text-sm last:border-0">
                      <span className="font-mono text-gray-800">{l.package_name}</span>
                      <span className="font-mono text-xs text-gray-500">{l.package_version ?? "—"} · {l.active ? "ativa" : "inativa"}</span>
                    </div>
                  ))}
                </div>
              )}
              {canValidate && (
                <button onClick={() => validate.mutate("libraries")} disabled={validate.isPending}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50">
                  <RefreshCw size={14} /> Validar bibliotecas nos workers
                </button>
              )}
              <p className="text-xs text-gray-400">A validação executa um job distribuído que importa as libs em cada executor.</p>
            </div>
          )}

          {tab === "validacoes" && (
            <div className="space-y-2">
              {(validations ?? []).length === 0 ? (
                <p className="text-sm text-gray-400">Nenhuma validação executada para este cluster.</p>
              ) : (validations ?? []).map((v) => {
                const ok = v.status === "success";
                const running = ["queued", "running"].includes(v.status);
                return (
                  <div key={v.id} className="flex items-center justify-between gap-3 rounded-lg border border-gray-100 px-4 py-2.5">
                    <div className="flex items-center gap-2">
                      {running ? <RefreshCw size={15} className="animate-spin text-brand-500" /> : ok ? <CheckCircle2 size={15} className="text-emerald-500" /> : <XCircle size={15} className="text-red-500" />}
                      <div>
                        <p className="text-sm font-medium text-gray-800">{v.validation_type === "distributed" ? "Execução distribuída" : v.validation_type === "libraries" ? "Bibliotecas nos workers" : v.validation_type}</p>
                        <p className="text-xs text-gray-400">{fmtDate(v.finished_at ?? v.created_at)}</p>
                      </div>
                    </div>
                    <span className="text-xs text-gray-500">{v.worker_count_detected ?? "—"}/{v.worker_count_expected ?? "—"} workers</span>
                  </div>
                );
              })}
            </div>
          )}

          {tab === "config" && (
            <dl className="grid grid-cols-2 gap-x-6 gap-y-4">
              <Field label="Nome">{cluster.name}</Field>
              <Field label="Tipo">{cluster.type}</Field>
              <div className="col-span-full"><Field label="Master URL"><span className="break-all font-mono text-xs">{cluster.spark_master_url}</span></Field></div>
              <Field label="Workers esperados">{cluster.expected_workers ?? "—"}</Field>
              <Field label="Runtime padrão">{cluster.runtime_image ? <span className="font-mono text-xs">{cluster.runtime_image}</span> : "—"}</Field>
              <Field label="Ativo">{cluster.is_active ? "Sim" : "Não"}</Field>
              <Field label="Criado por">{cluster.created_by ?? "—"}</Field>
            </dl>
          )}
        </div>
      </div>
    </div>
  );
}
