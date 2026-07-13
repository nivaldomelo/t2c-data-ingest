import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { AlertCircle, Copy, Download, Eraser, Loader2, Play, Wand2 } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { PrimaryButton } from "@/components/ui";
import { cn } from "@/lib/cn";
import { QueryResultGrid, csvOf, usePolledQuery } from "@/features/data-lake/QueryResultGrid";
import type { DlQueryHistoryItem, DlQueryResult } from "@/features/data-lake/types";
import { QUERY_ACTIVE, fmtDate } from "@/features/data-lake/types";

const LIMITS = [10, 50, 100, 500, 1000];

// Formatação leve: quebra linha antes das cláusulas principais e maiúsculas nas palavras-chave.
function formatSql(sql: string): string {
  const clauses = ["from", "where", "group by", "order by", "having", "limit", "left join", "inner join", "join", "union"];
  let out = sql.replace(/\s+/g, " ").trim();
  for (const c of clauses) {
    out = out.replace(new RegExp(`\\s+${c}\\s+`, "gi"), `\n${c.toUpperCase()} `);
  }
  out = out.replace(/^\s*select\s+/i, "SELECT ");
  return out;
}

export function DataLakeQueryConsole({
  connectionId,
  initialSql = "SELECT 1",
  tableId,
}: {
  connectionId: number;
  initialSql?: string;
  tableId?: number;
}) {
  const [sql, setSql] = useState(initialSql);
  const [limit, setLimit] = useState(100);
  const [queryId, setQueryId] = useState<number | null>(null);
  const [enqueueError, setEnqueueError] = useState<string | null>(null);

  const enqueue = useMutation({
    mutationFn: () =>
      api.post<DlQueryResult>("/api/v1/data-lake/query", {
        connection_id: connectionId, sql, limit, table_id: tableId,
      }),
    onSuccess: (r) => { setQueryId(r.id); setEnqueueError(null); },
    onError: (e) => setEnqueueError(e instanceof ApiError ? e.message : "Erro ao enviar consulta."),
  });

  const polled = usePolledQuery(queryId);
  const result = polled.data;
  const running = enqueue.isPending || (result ? QUERY_ACTIVE(result.status) : false);

  const history = useQuery({
    queryKey: ["dl-query-history", connectionId, tableId, result?.status],
    queryFn: () =>
      api.get<DlQueryHistoryItem[]>(
        `/api/v1/data-lake/query-history?connection_id=${connectionId}${tableId ? `&table_id=${tableId}` : ""}&limit=8`,
      ),
  });

  function exportCsv() {
    if (!result) return;
    const blob = new Blob([csvOf(result)], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `consulta_${result.id}.csv`; a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-3">
      <div className="overflow-hidden rounded-xl border border-graphite-800 bg-graphite-950">
        <textarea
          value={sql}
          onChange={(e) => setSql(e.target.value)}
          spellCheck={false}
          rows={4}
          className="w-full resize-y bg-transparent px-4 py-3 font-mono text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none"
          placeholder="SELECT * FROM bronze.clientes LIMIT 100"
        />
        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-white/10 px-3 py-2">
          <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
            <span>Limite</span>
            <select
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
              className="rounded-md border border-white/10 bg-graphite-900 px-2 py-1 text-slate-200 focus:outline-none"
            >
              {LIMITS.map((l) => <option key={l} value={l}>{l}</option>)}
            </select>
            <span className="text-slate-500">timeout 60s · somente leitura · máx 1000</span>
            <span className="mx-1 h-4 w-px bg-white/10" />
            <button onClick={() => setSql(formatSql(sql))} title="Formatar SQL"
              className="inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-slate-300 hover:bg-white/10">
              <Wand2 size={13} /> Formatar
            </button>
            <button onClick={() => setSql("")} title="Limpar"
              className="inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-slate-300 hover:bg-white/10">
              <Eraser size={13} /> Limpar
            </button>
            <button onClick={() => navigator.clipboard.writeText(sql)} title="Copiar SQL"
              className="inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-slate-300 hover:bg-white/10">
              <Copy size={13} /> Copiar
            </button>
          </div>
          <PrimaryButton
            icon={running ? <Loader2 size={15} className="animate-spin" /> : <Play size={15} />}
            disabled={running || !sql.trim()}
            onClick={() => enqueue.mutate()}
          >
            {running ? "Executando…" : "Executar"}
          </PrimaryButton>
        </div>
      </div>

      {enqueueError && (
        <p className="flex items-center gap-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
          <AlertCircle size={15} /> {enqueueError}
        </p>
      )}

      {result && (
        <div className="space-y-2">
          {result.status === "failed" && (
            <p className="flex items-center gap-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
              <AlertCircle size={15} /> {result.error_message ?? "Falha na consulta."}
            </p>
          )}
          {result.status === "success" && (
            <>
              <div className="flex items-center justify-between text-xs text-gray-500">
                <span>
                  {result.rows_returned ?? result.rows.length} linha(s) · {result.duration_seconds ?? 0}s
                  {result.limit_applied ? ` · LIMIT ${result.limit_applied}` : ""}
                </span>
                <div className="flex gap-1">
                  <button
                    onClick={() => navigator.clipboard.writeText(JSON.stringify(result.rows, null, 2))}
                    className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-gray-500 hover:bg-gray-100"
                  >
                    <Copy size={13} /> Copiar
                  </button>
                  <button
                    onClick={exportCsv}
                    className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-gray-500 hover:bg-gray-100"
                  >
                    <Download size={13} /> CSV
                  </button>
                </div>
              </div>
              <QueryResultGrid result={result} />
              {result.translated_sql && (
                <p className="font-mono text-[11px] text-gray-400">SQL executado: {result.translated_sql}</p>
              )}
            </>
          )}
          {QUERY_ACTIVE(result.status) && (
            <p className="flex items-center gap-2 px-1 py-2 text-sm text-gray-500">
              <Loader2 size={15} className="animate-spin" /> Executando no Spark…
            </p>
          )}
        </div>
      )}

      {/* Histórico */}
      {(history.data?.length ?? 0) > 0 && (
        <div>
          <p className="mb-1.5 mt-3 text-xs font-semibold uppercase tracking-wide text-gray-400">Últimas consultas</p>
          <div className="space-y-1">
            {history.data!.map((h) => (
              <button
                key={h.id}
                onClick={() => setSql(h.executed_sql)}
                title="Reutilizar SQL"
                className="flex w-full items-center gap-2 rounded-md border border-gray-100 px-2.5 py-1.5 text-left text-xs hover:bg-gray-50"
              >
                <span className={cn(
                  "h-1.5 w-1.5 shrink-0 rounded-full",
                  h.status === "success" ? "bg-emerald-500" : h.status === "failed" ? "bg-red-500" : "bg-gray-300",
                )} />
                <span className="truncate font-mono text-gray-600">{h.executed_sql}</span>
                <span className="ml-auto shrink-0 text-gray-400">{fmtDate(h.created_at)}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
