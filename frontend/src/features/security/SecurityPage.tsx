import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, HelpCircle, Lightbulb, ShieldCheck, XCircle } from "lucide-react";

import { api } from "@/lib/api";
import { PageHeader, MetricCard } from "@/components/ui";
import { MetricCardSkeleton } from "@/components/ui/LoadingSkeleton";
import { cn } from "@/lib/cn";

interface ChecklistItem { key: string; ok: boolean | null; category: string; detail: string; recommendation: string | null }
interface Category { key: string; label: string }
interface Summary { ok: number; pending: number; na: number; total: number }
interface Checklist { items: ChecklistItem[]; categories: Category[]; summary: Summary }
interface Overview {
  secrets_active: number; connections_total: number; db_connections_without_tls: number;
  unauthorized_attempts: number; secret_rotations: number; code_secret_detections: number;
  connections_without_tls_list: { id: number; name: string; type: string }[];
}

const LABELS: Record<string, string> = {
  secrets_encrypted: "Secrets criptografados em repouso",
  secrets_not_in_api: "API nunca retorna secrets",
  no_cli_secrets: "Sem secrets na linha de comando do Spark",
  logs_sanitized: "Logs mascaram secrets",
  sensitive_columns_masked: "Colunas sensíveis mascaradas",
  workspace_guarded: "Workspace de código protegido",
  rbac_enabled: "RBAC validado no backend",
  quick_query_read_only: "Consulta rápida somente-leitura",
  audit_enabled: "Auditoria habilitada",
  spark_not_public: "Spark não exposto publicamente",
  s3_public_access_blocked: "S3 sem acesso público",
  retention_logs: "Retenção de logs de execução",
  retention_executions: "Retenção de execuções",
  retention_audit: "Retenção de auditoria",
};

function StatusPill({ ok }: { ok: boolean | null }) {
  if (ok === true) return <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-semibold text-emerald-700"><CheckCircle2 size={12} /> OK</span>;
  if (ok === false) return <span className="inline-flex items-center gap-1 rounded-full bg-red-50 px-2 py-0.5 text-[11px] font-semibold text-red-700"><XCircle size={12} /> Pendência</span>;
  return <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-700"><HelpCircle size={12} /> Infra externa</span>;
}

export default function SecurityPage() {
  const checklist = useQuery({ queryKey: ["sec", "checklist"], queryFn: () => api.get<Checklist>("/api/v1/security/checklist") });
  const overview = useQuery({ queryKey: ["sec", "overview"], queryFn: () => api.get<Overview>("/api/v1/security/overview") });

  const items = checklist.data?.items ?? [];
  const cats = checklist.data?.categories ?? [];
  const sum = checklist.data?.summary;
  const o = overview.data;
  const pct = sum && sum.total ? Math.round((sum.ok / sum.total) * 100) : 0;

  const cards = [
    { label: "Controles OK", v: sum?.ok ?? 0, tone: "success" as const, hint: "verificados no backend, não só visual" },
    { label: "Pendências", v: sum?.pending ?? 0, tone: (sum?.pending ? "danger" : undefined) as any, hint: "controles que exigem ação" },
    { label: "Infra externa", v: sum?.na ?? 0, tone: undefined, hint: "dependem da conta AWS/rede" },
    { label: "Secrets ativos", v: o?.secrets_active ?? 0, tone: undefined, hint: "origens/destinos com credencial cifrada" },
    { label: "Origens sem TLS", v: o?.db_connections_without_tls ?? 0, tone: (o?.db_connections_without_tls ? "danger" : undefined) as any, hint: "conexões de banco sem SSL" },
    { label: "Tentativas bloqueadas", v: o?.unauthorized_attempts ?? 0, tone: (o?.unauthorized_attempts ? "danger" : undefined) as any, hint: "acessos/execuções negados por RBAC" },
    { label: "Rotações de secret", v: o?.secret_rotations ?? 0, tone: undefined, hint: "credenciais rotacionadas (auditado)" },
    { label: "Secrets no código", v: o?.code_secret_detections ?? 0, tone: (o?.code_secret_detections ? "danger" : undefined) as any, hint: "segredos detectados no workspace" },
  ];

  return (
    <div>
      <PageHeader
        icon={<ShieldCheck size={22} />}
        title="Segurança"
        description="Postura de segurança do T2C Data Ingest. Cada controle é verificado no backend/worker — não é apenas ocultar botões."
      />

      {/* Resumo de postura */}
      {sum && (
        <div className="mb-4 flex flex-wrap items-center gap-4 rounded-2xl border border-gray-100 bg-white p-4">
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-extrabold tabular-nums text-gray-900">{pct}%</span>
            <span className="text-sm text-gray-500">dos controles OK</span>
          </div>
          <div className="h-2 min-w-[160px] flex-1 overflow-hidden rounded-full bg-gray-100">
            <div className="h-full rounded-full bg-emerald-500" style={{ width: `${pct}%` }} />
          </div>
          <div className="flex gap-4 text-sm">
            <span className="text-emerald-700"><b>{sum.ok}</b> OK</span>
            <span className={cn(sum.pending ? "text-red-700" : "text-gray-400")}><b>{sum.pending}</b> pendências</span>
            <span className="text-amber-700"><b>{sum.na}</b> infra externa</span>
          </div>
        </div>
      )}

      {/* Cards com legenda */}
      {overview.isLoading ? (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4 xl:grid-cols-8">{Array.from({ length: 8 }).map((_, i) => <MetricCardSkeleton key={i} />)}</div>
      ) : (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4 xl:grid-cols-8">
          {cards.map((c) => <MetricCard key={c.label} label={c.label} value={c.v} tone={c.tone} hint={c.hint} />)}
        </div>
      )}

      <div className="mt-6 grid grid-cols-1 gap-4 xl:grid-cols-3">
        {/* Checklist agrupado por categoria */}
        <div className="space-y-4 xl:col-span-2">
          {cats.map((cat) => {
            const catItems = items.filter((i) => i.category === cat.key);
            if (catItems.length === 0) return null;
            return (
              <div key={cat.key} className="rounded-2xl border border-gray-100 bg-white">
                <div className="border-b border-gray-100 px-4 py-2.5 text-sm font-semibold text-gray-800">{cat.label}</div>
                <ul className="divide-y divide-gray-50">
                  {catItems.map((i) => (
                    <li key={i.key} className="px-4 py-3">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-medium text-gray-800">{LABELS[i.key] ?? i.key}</p>
                        <StatusPill ok={i.ok} />
                      </div>
                      <p className="mt-0.5 text-xs leading-relaxed text-gray-500">{i.detail}</p>
                      {i.recommendation && (
                        <p className="mt-1 flex items-start gap-1.5 rounded-lg bg-amber-50 px-2 py-1 text-xs leading-relaxed text-amber-800">
                          <Lightbulb size={13} className="mt-0.5 shrink-0 text-amber-500" /> {i.recommendation}
                        </p>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
          {items.length === 0 && !checklist.isLoading && (
            <div className="rounded-2xl border border-gray-100 bg-white px-4 py-8 text-center text-sm text-gray-400">Sem dados.</div>
          )}
        </div>

        {/* Origens sem TLS */}
        <div className="rounded-2xl border border-gray-100 bg-white self-start">
          <div className="border-b border-gray-100 px-4 py-2.5 text-sm font-semibold text-gray-800">Origens de banco sem TLS</div>
          <div className="max-h-[420px] overflow-auto">
            {(o?.connections_without_tls_list ?? []).length === 0 ? (
              <p className="px-4 py-8 text-center text-sm text-gray-400">Todas as origens de banco usam TLS.</p>
            ) : (
              <ul className="divide-y divide-gray-50">
                {(o?.connections_without_tls_list ?? []).map((c) => (
                  <li key={c.id} className="flex items-center justify-between px-4 py-2 text-sm">
                    <span className="font-medium text-gray-800">{c.name}</span>
                    <span className="rounded px-1.5 py-0.5 text-[10px] font-semibold bg-amber-50 text-amber-700">{c.type} · sem TLS</span>
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
