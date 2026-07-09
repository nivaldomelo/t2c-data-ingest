import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  Loader2,
  MinusCircle,
  RefreshCw,
  ShieldCheck,
  XCircle,
} from "lucide-react";

import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import {
  DetailModalShell,
  JsonViewer,
  ModalField,
  ModalSection,
  SecondaryButton,
  StatusBadge,
} from "@/components/ui";

export interface Check {
  name: string;
  status: string;
  detail: string;
}
export interface DqResult {
  id: number;
  execution_id: number | null;
  job_id: number | null;
  job_name: string | null;
  table_name: string | null;
  tipo_ingestao: string | null;
  records_read: number | null;
  records_written: number | null;
  watermark_before: string | null;
  watermark_after: string | null;
  checks: Check[] | null;
  overall: string;
  created_at: string;
}

const CHECK_LABEL: Record<string, string> = {
  registros_lidos: "Registros lidos",
  gravados_vs_lidos: "Gravados × lidos",
  watermark_avancou: "Watermark avançou",
  status_job: "Status do job",
  reconcile_count: "Contagem origem × destino",
  pk_not_null: "PK sem nulos",
  pk_duplicates: "PK sem duplicidade",
};
const CHECK_TONE: Record<string, string> = {
  pass: "text-emerald-600",
  warn: "text-amber-600",
  fail: "text-red-600",
  skip: "text-gray-400",
};

function overallBadge(overall: string) {
  if (overall === "pass") return <StatusBadge status="success" label="OK" />;
  if (overall === "fail") return <StatusBadge status="failed" label="Falha" />;
  if (overall === "warn") return <StatusBadge status="timeout" label="Atenção" />;
  return <StatusBadge status="skipped" label={overall} />;
}

function CheckIcon({ status }: { status: string }) {
  if (status === "pass") return <CheckCircle2 size={15} className="text-emerald-500" />;
  if (status === "fail") return <XCircle size={15} className="text-red-500" />;
  if (status === "skip") return <MinusCircle size={15} className="text-gray-400" />;
  return <AlertTriangle size={15} className="text-amber-500" />;
}

function fmt(t: string): string {
  return new Date(t).toLocaleString("pt-BR");
}
function nf(n: number | null): string {
  return n == null ? "—" : n.toLocaleString("pt-BR");
}

/** Score derivado: proporção de checks aprovados sobre os avaliados (ignora skip). */
function deriveScore(checks: Check[] | null): number | null {
  if (!checks?.length) return null;
  const evaluated = checks.filter((c) => c.status !== "skip");
  if (!evaluated.length) return null;
  const passed = evaluated.filter((c) => c.status === "pass").length;
  return Math.round((passed / evaluated.length) * 100);
}

export function DataQualityDetailModal({
  resultId,
  seed,
  onClose,
}: {
  resultId: number | null;
  seed?: DqResult;
  onClose: () => void;
}) {
  const open = resultId != null;
  const query = useQuery({
    queryKey: ["dq-result", resultId],
    queryFn: () => api.get<DqResult>(`/api/v1/data-quality/results/${resultId}`),
    enabled: open,
    placeholderData: seed,
  });

  const data = query.data ?? seed;
  const loading = open && query.isLoading && !data;
  const errored = open && query.isError && !data;
  const score = deriveScore(data?.checks ?? null);
  const checks = data?.checks ?? [];

  return (
    <DetailModalShell
      open={open}
      onClose={onClose}
      icon={<ShieldCheck size={20} />}
      title={data?.table_name ?? "Detalhes da validação"}
      subtitle={data ? `Data Quality · avaliação #${data.id}` : "Data Quality"}
      status={data ? overallBadge(data.overall) : undefined}
      footer={
        data?.execution_id ? (
          <a href={`/executions/${data.execution_id}`} className="text-sm font-medium text-brand-600 hover:text-brand-700">
            Ver execução #{data.execution_id} →
          </a>
        ) : undefined
      }
    >
      {loading ? (
        <div className="flex flex-col items-center justify-center gap-3 py-16 text-gray-400">
          <Loader2 size={26} className="animate-spin text-brand-500" />
          <p className="text-sm">Carregando detalhes…</p>
        </div>
      ) : errored ? (
        <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
          <AlertTriangle size={26} className="text-red-500" />
          <p className="text-sm text-gray-600">Não foi possível carregar os detalhes deste registro.</p>
          <SecondaryButton onClick={() => query.refetch()}>
            <RefreshCw size={15} /> Tentar novamente
          </SecondaryButton>
        </div>
      ) : !data ? null : (
        <>
          <ModalSection title="Resumo">
            <dl className="grid grid-cols-2 gap-x-6 gap-y-4 md:grid-cols-4">
              <ModalField label="Tabela / ativo">
                <span className="font-mono text-xs">{data.table_name ?? "—"}</span>
              </ModalField>
              <ModalField label="Tipo de ingestão">{data.tipo_ingestao ?? "—"}</ModalField>
              <ModalField label="Job">{data.job_name ?? "—"}</ModalField>
              <ModalField label="Score">
                {score == null ? (
                  "—"
                ) : (
                  <span
                    className={cn(
                      "font-semibold",
                      score >= 100 ? "text-emerald-600" : score >= 80 ? "text-amber-600" : "text-red-600"
                    )}
                  >
                    {score}%
                  </span>
                )}
              </ModalField>
              <ModalField label="Execução">{data.execution_id ? `#${data.execution_id}` : "—"}</ModalField>
              <ModalField label="Data/hora">{fmt(data.created_at)}</ModalField>
            </dl>
          </ModalSection>

          <ModalSection title="Métricas">
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <div className="rounded-xl border border-gray-100 bg-gray-50/60 p-3">
                <p className="text-[11px] uppercase tracking-wide text-gray-400">Registros lidos</p>
                <p className="mt-1 text-xl font-bold text-gray-900">{nf(data.records_read)}</p>
              </div>
              <div className="rounded-xl border border-gray-100 bg-gray-50/60 p-3">
                <p className="text-[11px] uppercase tracking-wide text-gray-400">Registros gravados</p>
                <p className="mt-1 text-xl font-bold text-gray-900">{nf(data.records_written)}</p>
              </div>
              <div className="col-span-2 rounded-xl border border-gray-100 bg-gray-50/60 p-3">
                <p className="text-[11px] uppercase tracking-wide text-gray-400">Watermark</p>
                <p className="mt-1 truncate font-mono text-xs text-gray-700">
                  {data.watermark_before ?? "∅"} → {data.watermark_after ?? "mantido"}
                </p>
              </div>
            </div>
          </ModalSection>

          <ModalSection title="Regras e resultados">
            {checks.length === 0 ? (
              <p className="text-sm text-gray-400">Nenhum detalhe adicional disponível.</p>
            ) : (
              <div className="divide-y divide-gray-100 overflow-hidden rounded-xl border border-gray-100">
                {checks.map((c) => (
                  <div key={c.name} className="flex items-center gap-3 px-3 py-2.5 text-sm">
                    <CheckIcon status={c.status} />
                    <span className="w-52 shrink-0 font-medium text-gray-700">{CHECK_LABEL[c.name] ?? c.name}</span>
                    <span className={cn("w-14 shrink-0 text-xs font-semibold uppercase", CHECK_TONE[c.status])}>
                      {c.status}
                    </span>
                    <span className="min-w-0 flex-1 truncate text-xs text-gray-500">{c.detail}</span>
                  </div>
                ))}
              </div>
            )}
          </ModalSection>

          {checks.length > 0 && (
            <ModalSection title="Detalhes técnicos">
              <JsonViewer data={checks} label="checks" />
            </ModalSection>
          )}
        </>
      )}
    </DetailModalShell>
  );
}
