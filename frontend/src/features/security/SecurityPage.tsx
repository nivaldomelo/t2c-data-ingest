import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, HelpCircle, ShieldCheck, XCircle } from "lucide-react";

import { api } from "@/lib/api";
import { PageHeader, MetricCard } from "@/components/ui";
import { MetricCardSkeleton } from "@/components/ui/LoadingSkeleton";
import { cn } from "@/lib/cn";

interface ChecklistItem { key: string; ok: boolean | null; detail: string }
interface Checklist { items: ChecklistItem[]; checklist: Record<string, boolean | null> }
interface Overview {
  secrets_active: number; connections_total: number; db_connections_without_tls: number;
  unauthorized_attempts: number; secret_rotations: number; code_secret_detections: number;
  connections_without_tls_list: { id: number; name: string; type: string }[];
}

const LABELS: Record<string, string> = {
  secrets_encrypted: "Secrets criptografados em repouso",
  logs_sanitized: "Logs mascaram secrets",
  secrets_not_in_api: "API não retorna secrets",
  no_cli_secrets: "Sem secrets na linha de comando do Spark",
  rbac_enabled: "RBAC aplicado no backend",
  quick_query_read_only: "Consulta rápida somente-leitura",
  spark_not_public: "Spark não exposto publicamente",
  s3_public_access_blocked: "S3 sem acesso público",
  audit_enabled: "Auditoria habilitada",
  workspace_guarded: "Workspace protegido (path traversal / extensões)",
  retention_logs: "Retenção de logs de execução",
  retention_executions: "Retenção de execuções",
  retention_audit: "Retenção de auditoria",
};

function StatusIcon({ ok }: { ok: boolean | null }) {
  if (ok === true) return <CheckCircle2 size={18} className="text-emerald-500" />;
  if (ok === false) return <XCircle size={18} className="text-red-500" />;
  return <HelpCircle size={18} className="text-amber-500" />;
}

export default function SecurityPage() {
  const checklist = useQuery({ queryKey: ["sec", "checklist"], queryFn: () => api.get<Checklist>("/api/v1/security/checklist") });
  const overview = useQuery({ queryKey: ["sec", "overview"], queryFn: () => api.get<Overview>("/api/v1/security/overview") });

  const items = checklist.data?.items ?? [];
  const okCount = items.filter((i) => i.ok === true).length;
  const failCount = items.filter((i) => i.ok === false).length;
  const naCount = items.filter((i) => i.ok === null).length;
  const o = overview.data;

  const cards = [
    { label: "Controles OK", v: okCount, tone: "success" as const },
    { label: "Pendências", v: failCount, tone: (failCount ? "danger" : undefined) as any },
    { label: "Não verificável", v: naCount, tone: undefined },
    { label: "Secrets ativos", v: o?.secrets_active ?? 0, tone: undefined },
    { label: "Origens sem TLS", v: o?.db_connections_without_tls ?? 0, tone: (o?.db_connections_without_tls ? "danger" : undefined) as any },
    { label: "Tentativas bloqueadas", v: o?.unauthorized_attempts ?? 0, tone: (o?.unauthorized_attempts ? "danger" : undefined) as any },
    { label: "Rotações de secret", v: o?.secret_rotations ?? 0, tone: undefined },
    { label: "Secrets no código", v: o?.code_secret_detections ?? 0, tone: (o?.code_secret_detections ? "danger" : undefined) as any },
  ];

  return (
    <div>
      <PageHeader
        icon={<ShieldCheck size={22} />}
        title="Segurança"
        description="Postura de segurança do T2C Data Ingest: checklist de controles, secrets, rede/cluster e auditoria. Verificado no backend — não é apenas visual."
      />

      {overview.isLoading ? (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4 xl:grid-cols-8">{Array.from({ length: 8 }).map((_, i) => <MetricCardSkeleton key={i} />)}</div>
      ) : (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4 xl:grid-cols-8">
          {cards.map((c) => <MetricCard key={c.label} label={c.label} value={c.v} tone={c.tone} />)}
        </div>
      )}

      <div className="mt-6 grid grid-cols-1 gap-4 xl:grid-cols-3">
        {/* Checklist */}
        <div className="xl:col-span-2 rounded-2xl border border-gray-100 bg-white">
          <div className="border-b border-gray-100 px-4 py-2.5 text-sm font-semibold text-gray-800">Checklist de segurança</div>
          <ul className="divide-y divide-gray-50">
            {items.map((i) => (
              <li key={i.key} className="flex items-start gap-3 px-4 py-2.5">
                <StatusIcon ok={i.ok} />
                <div className="min-w-0">
                  <p className="text-sm font-medium text-gray-800">{LABELS[i.key] ?? i.key}</p>
                  <p className="text-xs leading-relaxed text-gray-500">{i.detail}</p>
                </div>
              </li>
            ))}
            {items.length === 0 && !checklist.isLoading && (
              <li className="px-4 py-8 text-center text-sm text-gray-400">Sem dados.</li>
            )}
          </ul>
        </div>

        {/* Origens sem TLS */}
        <div className="rounded-2xl border border-gray-100 bg-white">
          <div className="border-b border-gray-100 px-4 py-2.5 text-sm font-semibold text-gray-800">Origens de banco sem TLS</div>
          <div className="max-h-[360px] overflow-auto">
            {(o?.connections_without_tls_list ?? []).length === 0 ? (
              <p className="px-4 py-8 text-center text-sm text-gray-400">Todas as origens de banco usam TLS.</p>
            ) : (
              <ul className="divide-y divide-gray-50">
                {(o?.connections_without_tls_list ?? []).map((c) => (
                  <li key={c.id} className="flex items-center justify-between px-4 py-2 text-sm">
                    <span className="font-medium text-gray-800">{c.name}</span>
                    <span className={cn("rounded px-1.5 py-0.5 text-[10px] font-semibold", "bg-amber-50 text-amber-700")}>{c.type} · sem TLS</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <p className="border-t border-gray-100 px-4 py-2 text-[11px] leading-relaxed text-gray-400">
            Habilite <code>ssl_enabled</code> na origem quando o banco suportar. Em produção, prefira redes privadas e TLS.
          </p>
        </div>
      </div>
    </div>
  );
}
