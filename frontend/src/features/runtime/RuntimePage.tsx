import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle, Boxes, CheckCircle2, FileText, Hammer, Layers, Play, Plus,
  RefreshCw, ServerCog, Trash2, XCircle,
} from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { Card, EmptyState, Modal, PageHeader, PrimaryButton, SecondaryButton } from "@/components/ui";
import { cn } from "@/lib/cn";
import { useAuth } from "@/lib/auth";
import {
  BUILD_STATUS_LABEL, BUILD_STATUS_TONE,
  type RuntimeBuild, type RuntimeBuildDetail, type RuntimeLibrary,
  type RuntimeSummary, type RuntimeValidation,
} from "@/features/runtime/types";

type Tab = "libraries" | "requirements" | "builds" | "validation";
const TABS: { key: Tab; label: string; icon: typeof Boxes }[] = [
  { key: "libraries", label: "Bibliotecas", icon: Boxes },
  { key: "requirements", label: "requirements.txt", icon: FileText },
  { key: "builds", label: "Builds do Runtime", icon: Layers },
  { key: "validation", label: "Validação do Cluster", icon: ServerCog },
];

function fmt(t: string | null): string {
  return t ? new Date(t).toLocaleString("pt-BR") : "—";
}

function MetricCard({ label, value, tone }: { label: string; value: React.ReactNode; tone?: string }) {
  return (
    <Card className="p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-gray-400">{label}</p>
      <div className={cn("mt-2 text-xl font-bold", tone ?? "text-gray-900")}>{value}</div>
    </Card>
  );
}

function BuildBadge({ status }: { status: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium", BUILD_STATUS_TONE[status] ?? BUILD_STATUS_TONE.queued)}>
      <span className={cn("h-1.5 w-1.5 rounded-full", status === "building" && "animate-pulse", {
        building: "bg-brand-500", success: "bg-emerald-500", active: "bg-emerald-500",
        failed: "bg-red-500", queued: "bg-sky-500", deprecated: "bg-gray-400",
      }[status] ?? "bg-gray-400")} />
      {BUILD_STATUS_LABEL[status] ?? status}
    </span>
  );
}

export default function RuntimePage() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("libraries");
  const canWrite = can("ingest:runtime:libraries:write");
  const canBuild = can("ingest:runtime:build");
  const canActivate = can("ingest:runtime:activate");
  const canValidate = can("ingest:runtime:validate");

  const { data: summary } = useQuery({
    queryKey: ["runtime-summary"],
    queryFn: () => api.get<RuntimeSummary>("/api/v1/runtime/summary"),
    refetchInterval: 8000,
  });

  return (
    <div>
      <PageHeader
        icon={<ServerCog size={22} />}
        title="Ambiente de Execução"
        description="Gerencie o runtime do cluster Spark: bibliotecas, imagem Docker versionada e validação distribuída."
      />

      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <MetricCard label="Bibliotecas ativas" value={summary?.active_libraries ?? "—"} />
        <MetricCard label="Imagem ativa" value={<span className="truncate text-sm font-semibold" title={summary?.active_build ?? undefined}>{summary?.active_build ?? "Nenhuma"}</span>} />
        <MetricCard label="Workers esperados" value={summary?.workers_expected ?? "—"} />
        <MetricCard
          label="Última validação"
          tone={summary?.last_validation_status === "success" ? "text-emerald-600" : summary?.last_validation_status === "failed" ? "text-red-600" : "text-gray-900"}
          value={<span className="text-sm font-semibold">{summary?.last_validation_status ? (summary.last_validation_status === "success" ? "OK" : "Falhou") : "—"}</span>}
        />
      </div>

      <div className="mb-6 border-b border-gray-200">
        <nav className="-mb-px flex gap-1 overflow-x-auto">
          {TABS.map(({ key, label, icon: Icon }) => (
            <button key={key} onClick={() => setTab(key)}
              className={cn("inline-flex shrink-0 items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors",
                tab === key ? "border-brand-500 text-brand-600" : "border-transparent text-gray-500 hover:text-gray-700")}>
              <Icon size={16} /> {label}
            </button>
          ))}
        </nav>
      </div>

      {tab === "libraries" && <LibrariesTab canWrite={canWrite} />}
      {tab === "requirements" && <RequirementsTab canBuild={canBuild} onBuilt={() => { setTab("builds"); qc.invalidateQueries({ queryKey: ["runtime-builds"] }); }} />}
      {tab === "builds" && <BuildsTab canActivate={canActivate} />}
      {tab === "validation" && <ValidationTab canValidate={canValidate} expected={summary?.workers_expected ?? 3} />}
    </div>
  );
}

/* ── Bibliotecas ── */
function LibrariesTab({ canWrite }: { canWrite: boolean }) {
  const qc = useQueryClient();
  const [spec, setSpec] = useState("");
  const [error, setError] = useState<string | null>(null);
  const { data } = useQuery({ queryKey: ["runtime-libraries"], queryFn: () => api.get<RuntimeLibrary[]>("/api/v1/runtime/libraries") });
  const libs = data ?? [];

  const add = useMutation({
    mutationFn: () => api.post("/api/v1/runtime/libraries", { package_spec: spec.trim() }),
    onSuccess: () => { setSpec(""); setError(null); qc.invalidateQueries({ queryKey: ["runtime-libraries"] }); qc.invalidateQueries({ queryKey: ["runtime-summary"] }); },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Falha ao adicionar."),
  });
  const toggle = useMutation({
    mutationFn: (l: RuntimeLibrary) => api.patch(`/api/v1/runtime/libraries/${l.id}`, { active: !l.active }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["runtime-libraries"] }); qc.invalidateQueries({ queryKey: ["runtime-summary"] }); },
  });
  const remove = useMutation({
    mutationFn: (id: number) => api.del(`/api/v1/runtime/libraries/${id}`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["runtime-libraries"] }); qc.invalidateQueries({ queryKey: ["runtime-summary"] }); },
  });

  return (
    <div className="space-y-4">
      {canWrite && (
        <Card className="p-4">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <input value={spec} onChange={(e) => setSpec(e.target.value)} onKeyDown={(e) => e.key === "Enter" && spec.trim() && add.mutate()}
              placeholder="pandas==2.2.3  ·  requests>=2.32.0" className="flex-1 rounded-lg border border-gray-200 bg-white px-3 py-2 font-mono text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20" />
            <PrimaryButton icon={<Plus size={16} />} loading={add.isPending} disabled={!spec.trim()} onClick={() => add.mutate()}>Cadastrar biblioteca</PrimaryButton>
          </div>
          {error && <p className="mt-2 flex items-center gap-1.5 text-xs text-red-600"><AlertTriangle size={13} /> {error}</p>}
          <p className="mt-2 text-xs text-gray-400">Somente PyPI. As bibliotecas ativas compõem o requirements.txt da próxima imagem.</p>
        </Card>
      )}

      <Card className="overflow-hidden p-0">
        {libs.length === 0 ? (
          <EmptyState icon={<Boxes size={22} />} title="Nenhuma biblioteca" description="Cadastre as dependências Python do runtime do cluster." />
        ) : (
          <table className="min-w-full text-sm">
            <thead><tr className="border-b border-gray-100 bg-gray-50/70 text-xs uppercase text-gray-500">
              <th className="px-5 py-2.5 text-left">Pacote</th><th className="px-5 py-2.5 text-left">Versão</th>
              <th className="px-5 py-2.5 text-left">Spec</th><th className="px-5 py-2.5 text-left">Ativo</th>
              <th className="px-5 py-2.5 text-right">Ações</th>
            </tr></thead>
            <tbody>
              {libs.map((l) => (
                <tr key={l.id} className="border-b border-gray-50 last:border-0">
                  <td className="px-5 py-2.5 font-medium text-gray-900">{l.package_name}</td>
                  <td className="px-5 py-2.5 font-mono text-xs text-gray-600">{l.package_version ?? "—"}</td>
                  <td className="px-5 py-2.5 font-mono text-xs text-gray-500">{l.package_spec}</td>
                  <td className="px-5 py-2.5">
                    <button disabled={!canWrite} onClick={() => toggle.mutate(l)}
                      className={cn("rounded-full px-2 py-0.5 text-xs font-medium", l.active ? "bg-emerald-50 text-emerald-700" : "bg-gray-100 text-gray-500")}>
                      {l.active ? "Ativa" : "Inativa"}
                    </button>
                  </td>
                  <td className="px-5 py-2.5 text-right">
                    {canWrite && (
                      <button onClick={() => remove.mutate(l.id)} className="rounded-md border border-gray-200 bg-white p-1.5 text-gray-500 hover:bg-red-50 hover:text-red-600"><Trash2 size={13} /></button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}

/* ── requirements.txt ── */
function RequirementsTab({ canBuild, onBuilt }: { canBuild: boolean; onBuilt: () => void }) {
  const { data } = useQuery({ queryKey: ["runtime-requirements"], queryFn: () => api.get<{ content: string; library_count: number }>("/api/v1/runtime/requirements") });
  const build = useMutation({
    mutationFn: () => api.post("/api/v1/runtime/builds", {}),
    onSuccess: onBuilt,
  });
  return (
    <div className="space-y-4">
      <Card className="p-5">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-900">requirements.txt gerado ({data?.library_count ?? 0} bibliotecas ativas)</h2>
          {canBuild && <PrimaryButton icon={<Hammer size={16} />} loading={build.isPending} onClick={() => build.mutate()}>Criar build de imagem</PrimaryButton>}
        </div>
        <pre className="overflow-x-auto rounded-xl border border-graphite-800 bg-graphite-950 p-4 font-mono text-xs leading-relaxed text-slate-200">{data?.content || "# nenhuma biblioteca ativa"}</pre>
        <p className="mt-2 text-xs text-gray-400">O build gera a imagem versionada com estas libs + o código dos jobs embutidos.</p>
      </Card>
    </div>
  );
}

/* ── Builds ── */
function BuildsTab({ canActivate }: { canActivate: boolean }) {
  const qc = useQueryClient();
  const [logsFor, setLogsFor] = useState<number | null>(null);
  const { data } = useQuery({
    queryKey: ["runtime-builds"],
    queryFn: () => api.get<RuntimeBuild[]>("/api/v1/runtime/builds"),
    refetchInterval: (q) => ((q.state.data as RuntimeBuild[] | undefined)?.some((b) => ["queued", "building"].includes(b.status)) ? 3000 : false),
  });
  const activate = useMutation({
    mutationFn: (id: number) => api.post(`/api/v1/runtime/builds/${id}/activate`, {}),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["runtime-builds"] }); qc.invalidateQueries({ queryKey: ["runtime-summary"] }); },
  });
  const builds = data ?? [];

  return (
    <Card className="overflow-hidden p-0">
      {builds.length === 0 ? (
        <EmptyState icon={<Layers size={22} />} title="Nenhum build" description="Gere o requirements.txt e crie o primeiro build da imagem runtime." />
      ) : (
        <table className="min-w-full text-sm">
          <thead><tr className="border-b border-gray-100 bg-gray-50/70 text-xs uppercase text-gray-500">
            <th className="px-5 py-2.5 text-left">Versão</th><th className="px-5 py-2.5 text-left">Imagem</th>
            <th className="px-5 py-2.5 text-left">Status</th><th className="px-5 py-2.5 text-left">Duração</th>
            <th className="px-5 py-2.5 text-left">Criado por</th><th className="px-5 py-2.5 text-right">Ações</th>
          </tr></thead>
          <tbody>
            {builds.map((b) => (
              <tr key={b.id} className="border-b border-gray-50 last:border-0">
                <td className="px-5 py-2.5 font-mono text-xs text-gray-700">{b.build_version}</td>
                <td className="px-5 py-2.5 font-mono text-xs text-gray-500">{b.image_full_name}</td>
                <td className="px-5 py-2.5"><BuildBadge status={b.is_active ? "active" : b.status} /></td>
                <td className="px-5 py-2.5 text-xs text-gray-500">{b.duration_seconds != null ? `${b.duration_seconds}s` : "—"}</td>
                <td className="px-5 py-2.5 text-xs text-gray-500">{b.created_by ?? "—"}</td>
                <td className="px-5 py-2.5 text-right">
                  <div className="flex justify-end gap-1.5">
                    <button onClick={() => setLogsFor(b.id)} className="rounded-md border border-gray-200 bg-white px-2.5 py-1 text-xs font-medium text-gray-600 hover:bg-gray-50">Logs</button>
                    {canActivate && b.status === "success" && !b.is_active && (
                      <button onClick={() => activate.mutate(b.id)} className="rounded-md border border-emerald-200 bg-white px-2.5 py-1 text-xs font-medium text-emerald-700 hover:bg-emerald-50">Ativar</button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {logsFor != null && <BuildLogsModal buildId={logsFor} onClose={() => setLogsFor(null)} />}
    </Card>
  );
}

function BuildLogsModal({ buildId, onClose }: { buildId: number; onClose: () => void }) {
  const { data } = useQuery({ queryKey: ["runtime-build", buildId], queryFn: () => api.get<RuntimeBuildDetail>(`/api/v1/runtime/builds/${buildId}`) });
  return (
    <Modal open onClose={onClose} title={`Build ${data?.build_version ?? ""}`} description={data?.image_full_name} width="max-w-3xl">
      <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-400">requirements.txt</h3>
      <pre className="mb-4 max-h-32 overflow-auto rounded-lg border border-gray-200 bg-gray-50 p-3 font-mono text-xs text-gray-700">{data?.requirements_snapshot || "—"}</pre>
      <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-400">Logs do build</h3>
      <pre className="max-h-[50vh] overflow-auto rounded-lg border border-graphite-800 bg-graphite-950 p-3 font-mono text-xs leading-relaxed text-slate-200 whitespace-pre-wrap break-words">{data?.build_logs || "Sem logs."}</pre>
    </Modal>
  );
}

/* ── Validação do Cluster ── */
function ValidationTab({ canValidate, expected }: { canValidate: boolean; expected: number }) {
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["runtime-validations"],
    queryFn: () => api.get<RuntimeValidation[]>("/api/v1/runtime/validations"),
    refetchInterval: (q) => ((q.state.data as RuntimeValidation[] | undefined)?.some((v) => ["queued", "running"].includes(v.status)) ? 3000 : false),
  });
  const run = useMutation({
    mutationFn: (type: string) => api.post("/api/v1/runtime/validations", { validation_type: type }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["runtime-validations"] }); qc.invalidateQueries({ queryKey: ["runtime-summary"] }); },
  });
  const runAll = async () => { await run.mutateAsync("distributed"); await run.mutateAsync("libraries"); };
  const vals = data ?? [];

  return (
    <div className="space-y-4">
      {canValidate && (
        <Card className="p-4">
          <div className="flex flex-wrap items-center gap-2">
            <span className="mr-2 text-sm text-gray-600">Workers esperados: <b>{expected}</b></span>
            <SecondaryButton icon={<Play size={15} />} loading={run.isPending} onClick={() => run.mutate("distributed")}>Validar execução distribuída</SecondaryButton>
            <SecondaryButton icon={<Boxes size={15} />} loading={run.isPending} onClick={() => run.mutate("libraries")}>Validar bibliotecas</SecondaryButton>
            <PrimaryButton icon={<ServerCog size={15} />} loading={run.isPending} onClick={runAll}>Validar tudo</PrimaryButton>
          </div>
        </Card>
      )}
      {vals.length === 0 ? (
        <EmptyState icon={<ServerCog size={22} />} title="Nenhuma validação" description="Rode uma validação para confirmar que o cluster está consistente." />
      ) : vals.map((v) => <ValidationCard key={v.id} v={v} />)}
    </div>
  );
}

function ValidationCard({ v }: { v: RuntimeValidation }) {
  const ok = v.status === "success";
  const running = ["queued", "running"].includes(v.status);
  const byHost = (v.workers_result && (v.workers_result as Record<string, unknown>)) || {};
  const hosts = v.validation_type === "distributed" ? byHost : (byHost as { by_host?: Record<string, unknown> }).by_host ?? {};
  const failures = (byHost as { failures?: { host: string; lib: string; error: string }[] }).failures ?? [];
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {running ? <RefreshCw size={16} className="animate-spin text-brand-500" /> : ok ? <CheckCircle2 size={16} className="text-emerald-500" /> : <XCircle size={16} className="text-red-500" />}
          <span className="text-sm font-semibold text-gray-900">
            {v.validation_type === "distributed" ? "Execução distribuída" : "Bibliotecas nos workers"}
          </span>
          <span className="text-xs text-gray-400">{fmt(v.finished_at ?? v.created_at)}</span>
        </div>
        <span className="text-xs text-gray-500">detectados {v.worker_count_detected ?? "—"}/{v.worker_count_expected ?? "—"}</span>
      </div>
      {Object.keys(hosts).length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {Object.entries(hosts as Record<string, unknown>).map(([host, val]) => (
            <span key={host} className="rounded-lg border border-gray-200 bg-gray-50 px-2.5 py-1 font-mono text-xs text-gray-600">
              {host}{typeof val === "number" ? `: ${val} part.` : ""}
            </span>
          ))}
        </div>
      )}
      {failures.length > 0 && (
        <div className="mt-3 space-y-1">
          {failures.slice(0, 8).map((f, i) => (
            <p key={i} className="text-xs text-red-600">✗ {f.lib} ausente em {f.host}</p>
          ))}
        </div>
      )}
      {v.error_message && !failures.length && <p className="mt-2 text-xs text-red-600">{v.error_message}</p>}
    </Card>
  );
}
