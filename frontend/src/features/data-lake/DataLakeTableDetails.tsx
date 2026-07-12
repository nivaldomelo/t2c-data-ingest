import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Columns3, Database, FileText, FolderTree, Loader2, PlayCircle, Table2, Terminal,
} from "lucide-react";

import { api } from "@/lib/api";
import { PrimaryButton, SecondaryButton } from "@/components/ui";
import { cn } from "@/lib/cn";
import type { Page } from "@/lib/api";
import { DataLakeQueryConsole } from "@/features/data-lake/DataLakeQueryConsole";
import { QueryResultGrid, usePolledQuery } from "@/features/data-lake/QueryResultGrid";
import type {
  DlColumn, DlFile, DlPartition, DlTable,
} from "@/features/data-lake/types";
import { QUERY_ACTIVE, fmtBytes, fmtDate } from "@/features/data-lake/types";

type Tab = "resumo" | "colunas" | "dados" | "particoes" | "arquivos" | "consulta";

export function DataLakeTableDetails({ tableId, canQuery }: { tableId: number; canQuery: boolean }) {
  const [tab, setTab] = useState<Tab>("resumo");
  const table = useQuery({
    queryKey: ["dl-table", tableId],
    queryFn: () => api.get<DlTable>(`/api/v1/data-lake/tables/${tableId}`),
  });

  const TABS: { id: Tab; label: string; icon: typeof Table2; hidden?: boolean }[] = [
    { id: "resumo", label: "Resumo", icon: Table2 },
    { id: "colunas", label: "Colunas", icon: Columns3 },
    { id: "dados", label: "Dados", icon: PlayCircle, hidden: !canQuery },
    { id: "particoes", label: "Partições", icon: FolderTree },
    { id: "arquivos", label: "Arquivos", icon: FileText },
    { id: "consulta", label: "Consulta rápida", icon: Terminal, hidden: !canQuery },
  ];

  if (table.isLoading || !table.data) {
    return (
      <div className="flex items-center gap-2 rounded-2xl border border-gray-100 bg-white p-10 text-sm text-gray-400">
        <Loader2 size={16} className="animate-spin" /> Carregando tabela…
      </div>
    );
  }
  const t = table.data;

  return (
    <div className="rounded-2xl border border-gray-100 bg-white">
      <div className="border-b border-gray-100 px-5 pt-4">
        <div className="flex items-center gap-2">
          <Database size={16} className="text-sky-500" />
          <h2 className="text-lg font-semibold text-gray-900">{t.full_name ?? t.table_name}</h2>
          <span className="rounded-md bg-gray-100 px-2 py-0.5 text-xs font-medium uppercase text-gray-500">{t.file_format}</span>
        </div>
        <p className="mt-0.5 break-all font-mono text-xs text-gray-400">{t.table_path}</p>
        <div className="mt-3 flex gap-1 overflow-x-auto">
          {TABS.filter((x) => !x.hidden).map((x) => {
            const Icon = x.icon;
            return (
              <button
                key={x.id}
                onClick={() => setTab(x.id)}
                className={cn(
                  "-mb-px flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium transition-colors",
                  tab === x.id ? "border-brand-500 text-brand-600" : "border-transparent text-gray-500 hover:text-gray-700",
                )}
              >
                <Icon size={15} /> {x.label}
              </button>
            );
          })}
        </div>
      </div>

      <div className="p-5">
        {tab === "resumo" && <ResumoTab t={t} />}
        {tab === "colunas" && <ColunasTab tableId={tableId} />}
        {tab === "dados" && canQuery && <DadosTab tableId={tableId} />}
        {tab === "particoes" && <ParticoesTab tableId={tableId} />}
        {tab === "arquivos" && <ArquivosTab tableId={tableId} />}
        {tab === "consulta" && canQuery && t.connection_id != null && (
          <DataLakeQueryConsole
            connectionId={t.connection_id}
            tableId={t.id}
            initialSql={`SELECT * FROM ${t.schema_name}.${t.table_name} LIMIT 100`}
          />
        )}
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-gray-100 bg-gray-50/50 px-3 py-2.5">
      <div className="text-[11px] font-medium uppercase tracking-wide text-gray-400">{label}</div>
      <div className="mt-0.5 text-sm font-semibold text-gray-800">{value}</div>
    </div>
  );
}

function ResumoTab({ t }: { t: DlTable }) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Camada" value={t.layer_name ?? t.schema_name ?? "—"} />
        <Stat label="Formato" value={t.file_format} />
        <Stat label="Arquivos" value={t.files_count ?? "—"} />
        <Stat label="Tamanho total" value={fmtBytes(t.total_size_bytes)} />
        <Stat label="Colunas" value={t.columns_count ?? "—"} />
        <Stat label="Registros estimados" value={t.estimated_rows ?? "—"} />
        <Stat label="Partições" value={(t.partition_columns ?? []).join(", ") || "—"} />
        <Stat label="Última atualização" value={fmtDate(t.last_modified_at)} />
      </div>
      <dl className="grid grid-cols-1 gap-x-4 gap-y-2 text-sm sm:grid-cols-2">
        <Detail label="Path S3" value={t.table_path} mono />
        <Detail label="Bucket" value={t.bucket_name ?? "—"} mono />
        <Detail label="Última varredura do catálogo" value={fmtDate(t.last_schema_scan_at)} />
        <Detail label="Status" value={t.status} />
      </dl>
    </div>
  );
}

function Detail({ label, value, mono }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div>
      <dt className="text-[11px] font-medium uppercase tracking-wide text-gray-400">{label}</dt>
      <dd className={cn("mt-0.5 text-gray-700", mono && "break-all font-mono text-xs")}>{value}</dd>
    </div>
  );
}

function ColunasTab({ tableId }: { tableId: number }) {
  const cols = useQuery({
    queryKey: ["dl-columns", tableId],
    queryFn: () => api.get<DlColumn[]>(`/api/v1/data-lake/tables/${tableId}/columns`),
  });
  if (cols.isLoading) return <Loading />;
  const data = cols.data ?? [];
  if (!data.length) return <Empty text="Nenhuma coluna. Execute a varredura do catálogo." />;
  return (
    <div className="overflow-hidden rounded-xl border border-gray-100">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 text-left text-xs uppercase tracking-wide text-gray-400">
          <tr>
            <th className="px-3 py-2 font-medium">#</th>
            <th className="px-3 py-2 font-medium">Coluna</th>
            <th className="px-3 py-2 font-medium">Tipo Spark</th>
            <th className="px-3 py-2 font-medium">Nullable</th>
            <th className="px-3 py-2 font-medium">Partição</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-50">
          {data.map((c) => (
            <tr key={c.id}>
              <td className="px-3 py-1.5 tabular-nums text-gray-400">{(c.ordinal_position ?? 0) + 1}</td>
              <td className="px-3 py-1.5 font-mono text-xs text-gray-800">{c.column_name}</td>
              <td className="px-3 py-1.5 font-mono text-xs text-gray-600">{c.spark_type}</td>
              <td className="px-3 py-1.5 text-gray-500">{c.nullable === false ? "não" : "sim"}</td>
              <td className="px-3 py-1.5">
                {c.is_partition && (
                  <span className="rounded bg-violet-50 px-1.5 py-0.5 text-[10px] font-semibold text-violet-700">partição</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ParticoesTab({ tableId }: { tableId: number }) {
  const parts = useQuery({
    queryKey: ["dl-partitions", tableId],
    queryFn: () => api.get<DlPartition[]>(`/api/v1/data-lake/tables/${tableId}/partitions`),
  });
  if (parts.isLoading) return <Loading />;
  const data = parts.data ?? [];
  if (!data.length) return <Empty text="Nenhuma partição detectada." />;
  return (
    <div className="overflow-hidden rounded-xl border border-gray-100">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 text-left text-xs uppercase tracking-wide text-gray-400">
          <tr>
            <th className="px-3 py-2 font-medium">Partição</th>
            <th className="px-3 py-2 text-right font-medium">Arquivos</th>
            <th className="px-3 py-2 text-right font-medium">Tamanho</th>
            <th className="px-3 py-2 text-right font-medium">Modificado</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-50">
          {data.map((p) => (
            <tr key={p.id}>
              <td className="px-3 py-1.5 font-mono text-xs text-gray-700">{p.partition_path}</td>
              <td className="px-3 py-1.5 text-right tabular-nums text-gray-500">{p.files_count ?? "—"}</td>
              <td className="px-3 py-1.5 text-right tabular-nums text-gray-500">{fmtBytes(p.total_size_bytes)}</td>
              <td className="px-3 py-1.5 text-right text-xs text-gray-400">{fmtDate(p.last_modified_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ArquivosTab({ tableId }: { tableId: number }) {
  const [page, setPage] = useState(1);
  const files = useQuery({
    queryKey: ["dl-files", tableId, page],
    queryFn: () => api.get<Page<DlFile>>(`/api/v1/data-lake/tables/${tableId}/files?page=${page}&page_size=50`),
  });
  if (files.isLoading) return <Loading />;
  const data = files.data;
  if (!data || data.total === 0) return <Empty text="Nenhum arquivo encontrado." />;
  return (
    <div className="space-y-2">
      <div className="overflow-hidden rounded-xl border border-gray-100">
        <div className="max-h-[420px] overflow-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-gray-50 text-left text-xs uppercase tracking-wide text-gray-400">
              <tr>
                <th className="px-3 py-2 font-medium">Arquivo</th>
                <th className="px-3 py-2 text-right font-medium">Tamanho</th>
                <th className="px-3 py-2 text-right font-medium">Modificado</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {data.items.map((f) => (
                <tr key={f.id}>
                  <td className="px-3 py-1.5 font-mono text-xs text-gray-700">{f.object_key}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums text-gray-500">{fmtBytes(f.size_bytes)}</td>
                  <td className="px-3 py-1.5 text-right text-xs text-gray-400">{fmtDate(f.last_modified_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <div className="flex items-center justify-between text-xs text-gray-500">
        <span>{data.total} arquivo(s)</span>
        <div className="flex items-center gap-2">
          <SecondaryButton disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Anterior</SecondaryButton>
          <span>página {data.page} / {data.total_pages}</span>
          <SecondaryButton disabled={!data.has_more} onClick={() => setPage((p) => p + 1)}>Próxima</SecondaryButton>
        </div>
      </div>
    </div>
  );
}

function DadosTab({ tableId }: { tableId: number }) {
  const [limit, setLimit] = useState(100);
  const [queryId, setQueryId] = useState<number | null>(null);
  const sample = useMutation({
    mutationFn: () => api.get<{ query_id: number | null; status: string }>(
      `/api/v1/data-lake/tables/${tableId}/sample?limit=${limit}`,
    ),
    onSuccess: (r) => setQueryId(r.query_id),
  });
  const polled = usePolledQuery(queryId);
  const result = polled.data;
  const running = sample.isPending || (result ? QUERY_ACTIVE(result.status) : false);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <PrimaryButton
          icon={running ? <Loader2 size={15} className="animate-spin" /> : <PlayCircle size={15} />}
          disabled={running}
          onClick={() => sample.mutate()}
        >
          {running ? "Carregando…" : queryId ? "Atualizar amostra" : "Carregar amostra"}
        </PrimaryButton>
        <select
          value={limit}
          onChange={(e) => setLimit(Number(e.target.value))}
          className="h-9 rounded-lg border border-gray-200 bg-white px-2 text-sm text-gray-700 focus:outline-none"
        >
          {[10, 50, 100, 500].map((l) => <option key={l} value={l}>{l} linhas</option>)}
        </select>
      </div>
      {result?.status === "failed" && (
        <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
          Não foi possível ler os arquivos Parquet desta tabela. {result.error_message}
        </p>
      )}
      {result?.status === "success" && (
        <>
          <p className="text-xs text-gray-500">{result.rows_returned ?? result.rows.length} linha(s) · {result.duration_seconds ?? 0}s</p>
          <QueryResultGrid result={result} />
        </>
      )}
      {!result && !running && <Empty text="Clique em “Carregar amostra” para visualizar os dados." />}
    </div>
  );
}

const Loading = () => (
  <div className="flex items-center gap-2 py-8 text-sm text-gray-400">
    <Loader2 size={15} className="animate-spin" /> Carregando…
  </div>
);
const Empty = ({ text }: { text: string }) => (
  <p className="py-8 text-center text-sm text-gray-400">{text}</p>
);
