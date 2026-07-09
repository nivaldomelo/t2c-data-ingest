import { Fragment, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, ShieldCheck, TrendingDown, TrendingUp, X, XCircle } from "lucide-react";

import { api, type Page } from "@/lib/api";
import { Card, EmptyState, PageHeader } from "@/components/ui";
import { cn } from "@/lib/cn";

interface Check { name: string; status: string; detail: string }
interface DqResult {
  id: number; execution_id: number | null; job_id: number | null; job_name: string | null;
  table_name: string | null; tipo_ingestao: string | null; records_read: number | null;
  records_written: number | null; watermark_before: string | null; watermark_after: string | null;
  checks: Check[] | null; overall: string; created_at: string;
}
interface Summary { total_7d: number; passed_7d: number; warn_7d: number; failed_7d: number; records_read_7d: number; records_written_7d: number }

const OVERALL: Record<string, { label: string; tone: string }> = {
  pass: { label: "OK", tone: "border-emerald-200 bg-emerald-50 text-emerald-700" },
  warn: { label: "Atenção", tone: "border-amber-200 bg-amber-50 text-amber-700" },
  fail: { label: "Falha", tone: "border-red-200 bg-red-50 text-red-700" },
};
const CHECK_TONE: Record<string, string> = { pass: "text-emerald-600", warn: "text-amber-600", fail: "text-red-600" };
const CHECK_LABEL: Record<string, string> = {
  registros_lidos: "Registros lidos", gravados_vs_lidos: "Gravados × lidos",
  watermark_avancou: "Watermark avançou", status_job: "Status do job",
};
function fmt(t: string): string { return new Date(t).toLocaleString("pt-BR"); }
function nf(n: number): string { return n.toLocaleString("pt-BR"); }

export default function DataQualityPage() {
  const [overall, setOverall] = useState("");
  const [expanded, setExpanded] = useState<number | null>(null);

  const q = useMemo(() => `page=1&page_size=50${overall ? `&overall=${overall}` : ""}`, [overall]);
  const { data, isLoading } = useQuery({ queryKey: ["dq-results", q], queryFn: () => api.get<Page<DqResult>>(`/api/v1/data-quality/results?${q}`) });
  const { data: s } = useQuery({ queryKey: ["dq-summary"], queryFn: () => api.get<Summary>("/api/v1/data-quality/summary") });
  const rows = data?.items ?? [];

  return (
    <div>
      <PageHeader icon={<ShieldCheck size={22} />} title="Data Quality" description="Validações de qualidade por execução e linhagem enviada ao t2c_data." />

      <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Card className="p-4"><p className="text-xs uppercase tracking-wide text-gray-400">Avaliações (7d)</p><p className="mt-1.5 text-2xl font-bold text-gray-900">{s?.total_7d ?? "—"}</p></Card>
        <Card className="p-4"><p className="text-xs uppercase tracking-wide text-gray-400">OK</p><p className="mt-1.5 text-2xl font-bold text-emerald-600">{s?.passed_7d ?? "—"}</p></Card>
        <Card className="p-4"><p className="text-xs uppercase tracking-wide text-gray-400">Atenção</p><p className="mt-1.5 text-2xl font-bold text-amber-600">{s?.warn_7d ?? "—"}</p></Card>
        <Card className="p-4"><p className="text-xs uppercase tracking-wide text-gray-400">Falha</p><p className="mt-1.5 text-2xl font-bold text-red-600">{s?.failed_7d ?? "—"}</p></Card>
        <Card className="p-4"><p className="flex items-center gap-1 text-xs uppercase tracking-wide text-gray-400"><TrendingDown size={12} /> Lidos (7d)</p><p className="mt-1.5 text-2xl font-bold text-gray-900">{s ? nf(s.records_read_7d) : "—"}</p></Card>
        <Card className="p-4"><p className="flex items-center gap-1 text-xs uppercase tracking-wide text-gray-400"><TrendingUp size={12} /> Gravados (7d)</p><p className="mt-1.5 text-2xl font-bold text-gray-900">{s ? nf(s.records_written_7d) : "—"}</p></Card>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <span className="text-sm text-gray-500">Filtrar:</span>
        {[["", "Todos"], ["pass", "OK"], ["warn", "Atenção"], ["fail", "Falha"]].map(([v, l]) => (
          <button key={v} onClick={() => setOverall(v)} className={cn("rounded-full border px-3 py-1 text-xs font-medium", overall === v ? "border-brand-500 bg-brand-50 text-brand-700" : "border-gray-200 bg-white text-gray-600 hover:bg-gray-50")}>{l}</button>
        ))}
      </div>

      <Card className="overflow-hidden p-0">
        {isLoading ? <div className="p-6 text-sm text-gray-400">Carregando…</div> : rows.length === 0 ? (
          <EmptyState icon={<ShieldCheck size={22} />} title="Nenhuma avaliação" description="As validações de qualidade aparecerão aqui após execuções de ingestão." />
        ) : (
          <table className="min-w-full text-sm">
            <thead><tr className="border-b border-gray-100 bg-gray-50/70 text-xs uppercase text-gray-500">
              <th className="px-5 py-2.5 text-left">Tabela</th><th className="px-5 py-2.5 text-left">Tipo</th>
              <th className="px-5 py-2.5 text-center">Lidos</th><th className="px-5 py-2.5 text-center">Gravados</th>
              <th className="px-5 py-2.5 text-left">Resultado</th><th className="px-5 py-2.5 text-left">Quando</th>
              <th className="px-5 py-2.5 text-right">Checks</th>
            </tr></thead>
            <tbody>
              {rows.map((r) => {
                const o = OVERALL[r.overall] ?? OVERALL.pass;
                return (
                  <Fragment key={r.id}>
                    <tr className="border-b border-gray-50 last:border-0">
                      <td className="px-5 py-2.5"><span className="font-mono text-xs text-gray-800">{r.table_name ?? "—"}</span><div className="text-[11px] text-gray-400">{r.job_name}</div></td>
                      <td className="px-5 py-2.5 text-xs text-gray-600">{r.tipo_ingestao ?? "—"}</td>
                      <td className="px-5 py-2.5 text-center text-sm">{r.records_read ?? "—"}</td>
                      <td className="px-5 py-2.5 text-center text-sm">{r.records_written ?? "—"}</td>
                      <td className="px-5 py-2.5"><span className={cn("inline-flex rounded-full border px-2.5 py-0.5 text-xs font-medium", o.tone)}>{o.label}</span></td>
                      <td className="px-5 py-2.5 text-xs text-gray-500">{fmt(r.created_at)}</td>
                      <td className="px-5 py-2.5 text-right"><button onClick={() => setExpanded(expanded === r.id ? null : r.id)} className="text-xs font-medium text-brand-600 hover:text-brand-700">{expanded === r.id ? "ocultar" : "ver"}</button></td>
                    </tr>
                    {expanded === r.id && (
                      <tr><td colSpan={7} className="bg-gray-50/60 px-5 py-3">
                        <div className="space-y-1">
                          {(r.checks ?? []).map((c) => (
                            <div key={c.name} className="flex items-center gap-2 text-sm">
                              {c.status === "pass" ? <CheckCircle2 size={14} className="text-emerald-500" /> : c.status === "fail" ? <XCircle size={14} className="text-red-500" /> : <X size={14} className="text-amber-500" />}
                              <span className="w-40 font-medium text-gray-700">{CHECK_LABEL[c.name] ?? c.name}</span>
                              <span className={cn("text-xs font-medium", CHECK_TONE[c.status])}>{c.status}</span>
                              <span className="text-xs text-gray-400">{c.detail}</span>
                            </div>
                          ))}
                          <p className="pt-1 text-xs text-gray-400">Watermark: {r.watermark_before ?? "∅"} → {r.watermark_after ?? "mantido"} · <a href={r.execution_id ? `/executions/${r.execution_id}` : "#"} className="text-brand-600">execução #{r.execution_id}</a></p>
                        </div>
                      </td></tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
