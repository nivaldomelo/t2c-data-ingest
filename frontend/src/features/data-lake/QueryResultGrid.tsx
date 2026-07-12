import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { DlQueryResult } from "@/features/data-lake/types";
import { QUERY_ACTIVE } from "@/features/data-lake/types";

/** Poll a Data Lake query until it finishes. */
export function usePolledQuery(queryId: number | null) {
  return useQuery({
    queryKey: ["dl-query", queryId],
    queryFn: () => api.get<DlQueryResult>(`/api/v1/data-lake/queries/${queryId}`),
    enabled: queryId != null,
    refetchInterval: (query) => (QUERY_ACTIVE(query.state.data?.status ?? "queued") ? 1500 : false),
  });
}

export function csvOf(result: DlQueryResult): string {
  const cols = result.columns.map((c) => c.name);
  const esc = (v: unknown) => {
    const s = v == null ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lines = [cols.join(",")];
  for (const row of result.rows) lines.push(cols.map((c) => esc(row[c])).join(","));
  return lines.join("\n");
}

export function QueryResultGrid({ result }: { result: DlQueryResult }) {
  if (!result.columns.length) {
    return <p className="px-3 py-6 text-center text-sm text-gray-400">Sem colunas no resultado.</p>;
  }
  return (
    <div className="overflow-hidden rounded-xl border border-gray-100">
      <div className="max-h-[420px] overflow-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-gray-50 text-left text-xs uppercase tracking-wide text-gray-400">
            <tr>
              {result.columns.map((c) => (
                <th key={c.name} className="whitespace-nowrap px-3 py-2 font-medium">
                  {c.name}
                  <span className="ml-1 font-normal normal-case text-gray-300">{c.type}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {result.rows.map((row, i) => (
              <tr key={i} className="hover:bg-gray-50/60">
                {result.columns.map((c) => (
                  <td key={c.name} className="whitespace-nowrap px-3 py-1.5 font-mono text-xs text-gray-700">
                    {formatCell(row[c.name])}
                  </td>
                ))}
              </tr>
            ))}
            {result.rows.length === 0 && (
              <tr>
                <td colSpan={result.columns.length} className="px-3 py-6 text-center text-sm text-gray-400">
                  Nenhuma linha retornada.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function formatCell(v: unknown): string {
  if (v == null) return "∅";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}
