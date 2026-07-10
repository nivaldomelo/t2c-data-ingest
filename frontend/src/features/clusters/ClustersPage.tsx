import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Cpu, Database, MemoryStick, Plug, RefreshCw, Server, Users } from "lucide-react";

import { api, type Page } from "@/lib/api";
import { Card, EmptyState, PageHeader, PrimaryButton, SecondaryButton } from "@/components/ui";
import { cn } from "@/lib/cn";
import { useAuth } from "@/lib/auth";
import { ClusterDetailModal } from "@/features/clusters/ClusterDetailModal";
import { CLUSTER_STATUS, fmtDate, type Cluster, type ClustersSummary } from "@/features/clusters/types";

function SummaryCard({ icon, label, value }: { icon: React.ReactNode; label: string; value: React.ReactNode }) {
  return (
    <Card className="p-4">
      <div className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-gray-400">
        <span className="text-gray-400">{icon}</span>{label}
      </div>
      <p className="mt-2 text-2xl font-bold text-gray-900">{value}</p>
    </Card>
  );
}

function StatusBadge({ status }: { status: string }) {
  const st = CLUSTER_STATUS[status] ?? CLUSTER_STATUS.inactive;
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium", st.tone)}>
      <span className={cn("h-1.5 w-1.5 rounded-full", st.dot, status === "validating" && "animate-pulse")} /> {st.label}
    </span>
  );
}

function Metric({ label, value, mono }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div>
      <dt className="text-[11px] font-medium uppercase tracking-wide text-gray-400">{label}</dt>
      <dd className={cn("mt-0.5 text-sm text-gray-800", mono && "font-mono text-xs")}>{value}</dd>
    </div>
  );
}

function ClusterCard({ cluster, canTest, onOpen, onTest, testing }: {
  cluster: Cluster; canTest: boolean; onOpen: () => void; onTest: () => void; testing: boolean;
}) {
  return (
    <div className="flex flex-col overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-card transition-shadow hover:shadow-card-hover">
      <div className="flex flex-1 flex-col p-5">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-brand-50 text-brand-600"><Server size={18} /></span>
            <div>
              <h3 className="font-semibold text-gray-900">{cluster.name}</h3>
              <p className="font-mono text-xs text-gray-400">{cluster.spark_master_url}</p>
            </div>
          </div>
          <StatusBadge status={cluster.status} />
        </div>

        <dl className="mt-4 grid grid-cols-3 gap-y-3 text-sm">
          <Metric label="Tipo" value={cluster.type} mono />
          <Metric label="Ambiente" value={cluster.environment_label ?? "—"} />
          <Metric label="Workers" value={cluster.worker_count ?? "—"} />
          <Metric label="Cores" value={cluster.total_cores ?? "—"} />
          <Metric label="Spark" value={cluster.spark_version ?? "—"} />
          <Metric label="Python" value={cluster.python_version ?? "—"} />
        </dl>

        <div className="mt-3 flex flex-wrap gap-x-4 gap-y-0.5 border-t border-gray-50 pt-2.5 text-xs text-gray-400">
          <span>Última verificação: {fmtDate(cluster.last_checked_at)}</span>
          <span>Última validação: {cluster.last_validation_status ?? "Não validado"}</span>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 border-t border-gray-100 bg-gray-50/40 px-5 py-2.5">
        <button onClick={onOpen} className="inline-flex h-8 items-center justify-center gap-1.5 rounded-lg bg-brand-500 px-3 text-xs font-semibold text-white hover:bg-brand-600">Ver detalhes</button>
        {canTest && (
          <button onClick={onTest} disabled={testing} className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50">
            <Plug size={13} /> {testing ? "Testando…" : "Testar conexão"}
          </button>
        )}
        <button onClick={onOpen} className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 text-xs font-medium text-gray-700 hover:bg-gray-50">
          <Users size={13} /> Ver workers
        </button>
      </div>
    </div>
  );
}

export default function ClustersPage() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const canManage = can("ingest:clusters:manage");
  const canTest = can("ingest:clusters:test");
  const [detail, setDetail] = useState<Cluster | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ["clusters"],
    queryFn: () => api.get<Page<Cluster>>("/api/v1/clusters?page=1&page_size=50"),
  });
  const { data: summary } = useQuery({
    queryKey: ["clusters-summary"],
    queryFn: () => api.get<ClustersSummary>("/api/v1/clusters/summary"),
  });

  const test = useMutation({
    mutationFn: (id: number) => api.post<{ reachable: boolean; message: string; workers_detected: number | null }>(`/api/v1/clusters/${id}/test`, {}),
    onSuccess: (r) => {
      setToast(r.reachable ? `Conexão OK · ${r.workers_detected ?? 0} workers ativos` : `Falha: ${r.message}`);
      setTimeout(() => setToast(null), 4000);
      qc.invalidateQueries({ queryKey: ["clusters"] });
      qc.invalidateQueries({ queryKey: ["clusters-summary"] });
    },
  });

  const clusters = data?.items ?? [];

  return (
    <div>
      <PageHeader
        icon={<Server size={22} />}
        title="Clusters"
        description="Gerencie e acompanhe clusters Spark usados para executar jobs distribuídos."
        actions={
          <div className="flex items-center gap-2">
            <SecondaryButton icon={<RefreshCw size={15} className={isFetching ? "animate-spin" : ""} />}
              onClick={() => { refetch(); qc.invalidateQueries({ queryKey: ["clusters-summary"] }); }}>Atualizar status</SecondaryButton>
            {canManage && <PrimaryButton icon={<Server size={16} />} disabled title="Cadastro de cluster (em breve)">Novo cluster</PrimaryButton>}
          </div>
        }
      />

      {toast && <div className="mb-4 rounded-lg border border-brand-200 bg-brand-50 px-3.5 py-2 text-sm text-brand-800">{toast}</div>}

      <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <SummaryCard icon={<Server size={14} />} label="Total" value={summary?.total_clusters ?? "—"} />
        <SummaryCard icon={<Server size={14} />} label="Ativos" value={summary?.active_clusters ?? "—"} />
        <SummaryCard icon={<Users size={14} />} label="Workers" value={summary?.workers_total ?? "—"} />
        <SummaryCard icon={<Cpu size={14} />} label="Cores" value={summary?.cores_total ?? "—"} />
        <SummaryCard icon={<MemoryStick size={14} />} label="Memória" value={summary?.memory_total ?? "—"} />
        <SummaryCard icon={<Database size={14} />} label="Última validação" value={<span className="text-base">{summary?.last_validation_status === "success" ? "Sucesso" : summary?.last_validation_status === "failed" ? "Falha" : "Não validado"}</span>} />
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-52 animate-pulse rounded-2xl bg-gray-100" />)}
        </div>
      ) : clusters.length === 0 ? (
        <Card className="py-4">
          <EmptyState icon={<Server size={24} />} title="Nenhum cluster cadastrado"
            description="Cadastre um cluster Spark para executar jobs distribuídos." />
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
          {clusters.map((c) => (
            <ClusterCard key={c.id} cluster={c} canTest={canTest}
              testing={test.isPending && test.variables === c.id}
              onOpen={() => setDetail(c)} onTest={() => test.mutate(c.id)} />
          ))}
        </div>
      )}

      {detail && <ClusterDetailModal cluster={detail} open onClose={() => setDetail(null)} />}
    </div>
  );
}
