import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ShieldCheck, TrendingDown, TrendingUp } from "lucide-react";

import { api, type Page } from "@/lib/api";
import { Card, EmptyState, PageHeader } from "@/components/ui";
import { cn } from "@/lib/cn";
import { DataQualityDetailModal, type DqResult } from "@/features/data-quality/DataQualityDetailModal";

interface Summary { total_7d: number; passed_7d: number; warn_7d: number; failed_7d: number; records_read_7d: number; records_written_7d: number }

const OVERALL: Record<string, { label: string; tone: string }> = {
  pass: { label: "OK", tone: "border-emerald-200 bg-emerald-50 text-emerald-700" },
  warn: { label: "Atenção", tone: "border-amber-200 bg-amber-50 text-amber-700" },
  fail: { label: "Falha", tone: "border-red-200 bg-red-50 text-red-700" },
};
function fmt(t: string): string { return new Date(t).toLocaleString("pt-BR"); }
function nf(n: number): string { return n.toLocaleString("pt-BR"); }

export default function DataQualityPage() {
  const [overall, setOverall] = useState("");
  const [selected, setSelected] = useState<DqResult | null>(null);

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
              <th className="px-5 py-2.5 text-right">Detalhe</th>
            </tr></thead>
            <tbody>
              {rows.map((r) => {
                const o = OVERALL[r.overall] ?? OVERALL.pass;
                return (
                  <tr
                    key={r.id}
                    onClick={() => setSelected(r)}
                    className="cursor-pointer border-b border-gray-50 transition-colors last:border-0 hover:bg-gray-50/70"
                  >
                    <td className="px-5 py-2.5"><span className="font-mono text-xs text-gray-800">{r.table_name ?? "—"}</span><div className="text-[11px] text-gray-400">{r.job_name}</div></td>
                    <td className="px-5 py-2.5 text-xs text-gray-600">{r.tipo_ingestao ?? "—"}</td>
                    <td className="px-5 py-2.5 text-center text-sm">{r.records_read ?? "—"}</td>
                    <td className="px-5 py-2.5 text-center text-sm">{r.records_written ?? "—"}</td>
                    <td className="px-5 py-2.5"><span className={cn("inline-flex rounded-full border px-2.5 py-0.5 text-xs font-medium", o.tone)}>{o.label}</span></td>
                    <td className="px-5 py-2.5 text-xs text-gray-500">{fmt(r.created_at)}</td>
                    <td className="px-5 py-2.5 text-right">
                      <button
                        onClick={(e) => { e.stopPropagation(); setSelected(r); }}
                        className="text-xs font-medium text-brand-600 hover:text-brand-700"
                      >
                        Ver detalhes
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </Card>

      <DataQualityDetailModal resultId={selected?.id ?? null} seed={selected ?? undefined} onClose={() => setSelected(null)} />
    </div>
  );
}
