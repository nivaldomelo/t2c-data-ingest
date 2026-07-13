import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Check, Columns3, Copy, Database, FileText, FolderTree, HeartPulse, Loader2, MapPin,
  PlayCircle, RefreshCw, Table2, Terminal,
} from "lucide-react";

import { api } from "@/lib/api";
import { PrimaryButton, SecondaryButton } from "@/components/ui";
import { cn } from "@/lib/cn";
import type { Page } from "@/lib/api";
import { DataLakeQueryConsole } from "@/features/data-lake/DataLakeQueryConsole";
import { QueryResultGrid, usePolledQuery } from "@/features/data-lake/QueryResultGrid";
import type { DlColumn, DlFile, DlPartition, DlQueryResult, DlTable } from "@/features/data-lake/types";
import { QUERY_ACTIVE, fmtBytes, fmtDate, statusBadge } from "@/features/data-lake/types";

type Tab = "resumo" | "colunas" | "dados" | "particoes" | "arquivos" | "consulta";

function CopyBtn({ text, label }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1200); }}
      className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-xs text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
      title={`Copiar ${label ?? ""}`.trim()}
    >
      {copied ? <Check size={13} className="text-emerald-500" /> : <Copy size={13} />}
      {label && <span>{label}</span>}
    </button>
  );
}

function Badge({ children, tone = "gray" }: { children: React.ReactNode; tone?: "gray" | "brand" | "violet" | "sky" }) {
  const cls = {
    gray: "bg-gray-100 text-gray-600",
    brand: "bg-brand-50 text-brand-700",
    violet: "bg-violet-50 text-violet-700",
    sky: "bg-sky-50 text-sky-700",
  }[tone];
  return <span className={cn("rounded-md px-2 py-0.5 text-xs font-medium", cls)}>{children}</span>;
}

export function DataLakeTableDetails({ tableId, canQuery }: { tableId: number; canQuery: boolean }) {
  const [tab, setTab] = useState<Tab>("resumo");
  const qc = useQueryClient();
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
  const st = statusBadge(t.status);
  const partitioned = (t.partition_columns ?? []).length > 0;

  function refreshMeta() {
    qc.invalidateQueries({ queryKey: ["dl-table", tableId] });
    qc.invalidateQueries({ queryKey: ["dl-columns", tableId] });
    qc.invalidateQueries({ queryKey: ["dl-partitions", tableId] });
    qc.invalidateQueries({ queryKey: ["dl-files", tableId] });
  }

  return (
    <div className="rounded-2xl border border-gray-100 bg-white">
      {/* Cabeçalho da tabela */}
      <div className="border-b border-gray-100 px-5 pt-4">
        <div className="flex flex-wrap items-center gap-2">
          <Database size={18} className="text-sky-500" />
          <h2 className="text-lg font-semibold text-gray-900">{t.full_name ?? t.table_name}</h2>
          <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium ring-1", st.cls)}>{st.label}</span>
        </div>
        <p className="mt-0.5 text-sm text-gray-500">Tabela {t.file_format} no Data Lake</p>

        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          {t.layer_name && <Badge tone="brand">{t.layer_name}</Badge>}
          <Badge>{t.file_format}</Badge>
          {partitioned && <Badge tone="violet">Particionada</Badge>}
          <Badge tone="sky">S3</Badge>
        </div>

        <div className="mt-2 flex items-center gap-1 rounded-lg bg-gray-50 px-3 py-1.5">
          <MapPin size={13} className="shrink-0 text-gray-400" />
          <span className="truncate font-mono text-xs text-gray-600">{t.table_path}</span>
          <span className="ml-auto"><CopyBtn text={t.table_path} label="Copiar path" /></span>
        </div>

        <div className="mt-3 flex flex-wrap gap-2">
          {canQuery && (
            <SecondaryButton icon={<PlayCircle size={15} />} onClick={() => setTab("dados")}>Carregar amostra</SecondaryButton>
          )}
          {canQuery && (
            <SecondaryButton icon={<Terminal size={15} />} onClick={() => setTab("consulta")}>Consulta rápida</SecondaryButton>
          )}
          <SecondaryButton icon={<RefreshCw size={15} />} onClick={refreshMeta}>Atualizar metadados</SecondaryButton>
        </div>

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
        {tab === "dados" && canQuery && <DadosTab t={t} />}
        {tab === "particoes" && <ParticoesTab t={t} onOpenFiles={() => setTab("arquivos")} />}
        {tab === "arquivos" && <ArquivosTab tableId={tableId} />}
        {tab === "consulta" && canQuery && t.connection_id != null && (
          <DataLakeQueryConsole
            connectionId={t.connection_id}
            tableId={t.id}
            initialSql={`SELECT *\nFROM ${t.schema_name}.${t.table_name}\nLIMIT 100`}
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

function CardBox({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-gray-100 p-4">
      <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-gray-400">
        {icon} {title}
      </div>
      {children}
    </div>
  );
}

function KV({ label, value, copy }: { label: string; value: React.ReactNode; copy?: string }) {
  return (
    <div className="flex items-start justify-between gap-2 py-1">
      <span className="text-xs text-gray-400">{label}</span>
      <span className="flex items-center gap-1 text-right text-sm text-gray-700">
        <span className="break-all">{value}</span>
        {copy != null && copy !== "" && <CopyBtn text={copy} />}
      </span>
    </div>
  );
}

function ResumoTab({ t }: { t: DlTable }) {
  const lp = t.latest_partition;
  const ing = t.last_ingestion;
  const dq = t.quality;
  const scanAge = t.last_catalog_scan_at
    ? `atualizado ${fmtDate(t.last_catalog_scan_at)}`
    : "nunca escaneado";
  return (
    <div className="space-y-4">
      {/* Cards principais */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Camada" value={t.layer_name ?? t.schema_name ?? "—"} />
        <Stat label="Formato" value={t.file_format} />
        <Stat label="Arquivos" value={t.files_count ?? "—"} />
        <Stat label="Tamanho total" value={fmtBytes(t.total_size_bytes)} />
        <Stat label="Colunas" value={t.columns_count ?? "—"} />
        <Stat label="Partições" value={(t.partition_columns ?? []).join(", ") || "—"} />
        <Stat label="Última atualização" value={fmtDate(t.last_modified_at)} />
        <Stat label="Registros estimados" value={t.estimated_rows ?? "Não calculado"} />
      </div>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        {/* Localização */}
        <CardBox title="Localização" icon={<MapPin size={14} />}>
          <KV label="Bucket" value={<span className="font-mono text-xs">{t.bucket_name ?? "—"}</span>} copy={t.bucket_name ?? ""} />
          <KV label="Prefixo" value={<span className="font-mono text-xs">{t.base_prefix || "(raiz)"}</span>} copy={t.base_prefix ?? ""} />
          <KV label="Path S3" value={<span className="font-mono text-xs">{t.table_path}</span>} copy={t.table_path} />
          <KV label="Conexão" value={t.connection_name ?? "—"} />
        </CardBox>

        {/* Saúde da tabela */}
        <CardBox title="Saúde da tabela" icon={<HeartPulse size={14} />}>
          <KV label="Status" value={statusBadge(t.status).label} />
          <KV label="Schema" value={(t.columns_count ?? 0) > 0 ? "detectado" : "não detectado"} />
          <KV label="Partições" value={(t.partition_columns ?? []).length > 0 ? "detectadas" : "não particionada"} />
          <KV label="Arquivos" value={`${t.files_count ?? 0} encontrados`} />
          <KV label="Catálogo" value={scanAge} />
        </CardBox>

        {/* Última partição */}
        <CardBox title="Última partição" icon={<FolderTree size={14} />}>
          {lp ? (
            <>
              <KV label="Partição" value={<span className="font-mono text-xs">{lp.path}</span>} copy={lp.path} />
              <KV label="Arquivos" value={lp.files_count ?? "—"} />
              <KV label="Tamanho" value={fmtBytes(lp.total_size_bytes)} />
              <KV label="Data" value={fmtDate(lp.last_modified_at)} />
            </>
          ) : (
            <p className="text-sm text-gray-400">Última partição: não identificada.</p>
          )}
        </CardBox>

        {/* Origem operacional + qualidade */}
        <CardBox title="Última carga & qualidade" icon={<PlayCircle size={14} />}>
          {ing && (ing.job_name || ing.pipeline_name || ing.status) ? (
            <>
              <KV label="Job" value={ing.job_name ?? "—"} />
              <KV label="Pipeline" value={ing.pipeline_name ?? "—"} />
              <KV label="Status" value={ing.status ?? "—"} />
              <KV label="Registros gravados" value={ing.records_written ?? "—"} />
              <KV label="Executado em" value={fmtDate(ing.executed_at)} />
            </>
          ) : (
            <p className="text-sm text-gray-400">Nenhuma execução vinculada a esta tabela.</p>
          )}
          <div className="mt-2 border-t border-gray-100 pt-2">
            <KV
              label="Data Quality"
              value={dq && dq.last_status ? `${dq.score != null ? `${dq.score}% · ` : ""}${dq.last_status}` : "Não executado"}
            />
          </div>
        </CardBox>
      </div>
    </div>
  );
}

function ColunasTab({ tableId }: { tableId: number }) {
  const [q, setQ] = useState("");
  const cols = useQuery({
    queryKey: ["dl-columns", tableId],
    queryFn: () => api.get<DlColumn[]>(`/api/v1/data-lake/tables/${tableId}/columns`),
  });
  const data = useMemo(() => {
    const all = cols.data ?? [];
    const f = q.trim().toLowerCase();
    return f ? all.filter((c) => c.column_name.toLowerCase().includes(f)) : all;
  }, [cols.data, q]);

  if (cols.isLoading) return <Loading />;
  if (!(cols.data ?? []).length) return <Empty text="Nenhuma coluna. Execute a varredura do catálogo." />;
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Buscar coluna…"
          className="h-9 w-56 rounded-lg border border-gray-200 px-3 text-sm focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
        />
        <span className="text-xs text-gray-400">{data.length} de {cols.data!.length} colunas</span>
      </div>
      <div className="overflow-hidden rounded-xl border border-gray-100">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs uppercase tracking-wide text-gray-400">
              <tr>
                <th className="px-3 py-2 font-medium">#</th>
                <th className="px-3 py-2 font-medium">Coluna</th>
                <th className="px-3 py-2 font-medium">Tipo Spark</th>
                <th className="px-3 py-2 font-medium">Tipo Parquet</th>
                <th className="px-3 py-2 font-medium">Nullable</th>
                <th className="px-3 py-2 font-medium">Origem</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {data.map((c) => (
                <tr key={c.id} className="group">
                  <td className="px-3 py-1.5 tabular-nums text-gray-400">{(c.ordinal_position ?? 0) + 1}</td>
                  <td className="px-3 py-1.5">
                    <span className="font-mono text-xs text-gray-800">{c.column_name}</span>
                    <span className="ml-1 opacity-0 group-hover:opacity-100"><CopyBtn text={c.column_name} /></span>
                  </td>
                  <td className="px-3 py-1.5"><Badge>{c.spark_type ?? "—"}</Badge></td>
                  <td className="px-3 py-1.5 font-mono text-[11px] text-gray-500">{c.parquet_type ?? "—"}</td>
                  <td className="px-3 py-1.5 text-gray-500">{c.nullable === false ? "não" : "sim"}</td>
                  <td className="px-3 py-1.5">
                    {c.is_partition
                      ? <Badge tone="violet">Partição</Badge>
                      : <span className="text-xs text-gray-400">arquivo</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function ParticoesTab({ t, onOpenFiles }: { t: DlTable; onOpenFiles: () => void }) {
  const parts = useQuery({
    queryKey: ["dl-partitions", t.id],
    queryFn: () => api.get<DlPartition[]>(`/api/v1/data-lake/tables/${t.id}/partitions`),
  });
  const sorted = useMemo(
    () => [...(parts.data ?? [])].sort((a, b) => b.partition_path.localeCompare(a.partition_path)),
    [parts.data],
  );
  if (parts.isLoading) return <Loading />;
  if (!sorted.length) return <Empty text="Nenhuma partição detectada." />;
  return (
    <div className="overflow-hidden rounded-xl border border-gray-100">
      <div className="max-h-[440px] overflow-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-gray-50 text-left text-xs uppercase tracking-wide text-gray-400">
            <tr>
              <th className="px-3 py-2 font-medium">Partição</th>
              <th className="px-3 py-2 text-right font-medium">Arquivos</th>
              <th className="px-3 py-2 text-right font-medium">Tamanho</th>
              <th className="px-3 py-2 text-right font-medium">Modificação</th>
              <th className="px-3 py-2 text-right font-medium">Ações</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {sorted.map((p, i) => (
              <tr key={p.id} className="group">
                <td className="px-3 py-1.5 font-mono text-xs text-gray-700">
                  {p.partition_path}
                  {i === 0 && <span className="ml-2 rounded bg-brand-50 px-1.5 py-0.5 text-[10px] font-semibold text-brand-700">mais recente</span>}
                </td>
                <td className="px-3 py-1.5 text-right tabular-nums text-gray-500">{p.files_count ?? "—"}</td>
                <td className="px-3 py-1.5 text-right tabular-nums text-gray-500">{fmtBytes(p.total_size_bytes)}</td>
                <td className="px-3 py-1.5 text-right text-xs text-gray-400">{fmtDate(p.last_modified_at)}</td>
                <td className="px-3 py-1.5">
                  <div className="flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100">
                    <button onClick={onOpenFiles} className="rounded-md px-1.5 py-0.5 text-xs text-gray-500 hover:bg-gray-100" title="Ver arquivos">
                      <FileText size={13} />
                    </button>
                    <CopyBtn text={`${t.table_path}${p.partition_path}/`} />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ArquivosTab({ tableId }: { tableId: number }) {
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const files = useQuery({
    queryKey: ["dl-files", tableId, page],
    queryFn: () => api.get<Page<DlFile>>(`/api/v1/data-lake/tables/${tableId}/files?page=${page}&page_size=50`),
  });
  const rows = useMemo(() => {
    const items = files.data?.items ?? [];
    const f = q.trim().toLowerCase();
    return f ? items.filter((x) => x.object_key.toLowerCase().includes(f)) : items;
  }, [files.data, q]);

  if (files.isLoading) return <Loading />;
  const data = files.data;
  if (!data || data.total === 0) return <Empty text="Nenhum arquivo encontrado." />;
  return (
    <div className="space-y-2">
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Buscar por key…"
        className="h-9 w-64 rounded-lg border border-gray-200 px-3 text-sm focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
      />
      <div className="overflow-hidden rounded-xl border border-gray-100">
        <div className="max-h-[420px] overflow-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-gray-50 text-left text-xs uppercase tracking-wide text-gray-400">
              <tr>
                <th className="px-3 py-2 font-medium">Arquivo</th>
                <th className="px-3 py-2 text-right font-medium">Tamanho</th>
                <th className="px-3 py-2 text-right font-medium">Modificação</th>
                <th className="px-3 py-2 text-right font-medium">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {rows.map((f) => (
                <tr key={f.id} className="group">
                  <td className="px-3 py-1.5 font-mono text-xs text-gray-700">{f.object_key}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums text-gray-500">{fmtBytes(f.size_bytes)}</td>
                  <td className="px-3 py-1.5 text-right text-xs text-gray-400">{fmtDate(f.last_modified_at)}</td>
                  <td className="px-3 py-1.5 text-right">
                    <span className="opacity-0 group-hover:opacity-100"><CopyBtn text={f.object_key} label="key" /></span>
                  </td>
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

function partitionWhere(path: string): string {
  // "ano=2026/mes=07/dia=11" -> "ano = '2026' AND mes = '07' AND dia = '11'"
  return path
    .split("/")
    .filter((s) => s.includes("="))
    .map((s) => { const [k, v] = s.split("="); return `${k} = '${v}'`; })
    .join(" AND ");
}

function DadosTab({ t }: { t: DlTable }) {
  const [limit, setLimit] = useState(100);
  const [queryId, setQueryId] = useState<number | null>(null);

  const run = useMutation({
    mutationFn: (sql: string) =>
      api.post<DlQueryResult>("/api/v1/data-lake/query", {
        connection_id: t.connection_id, sql, limit, table_id: t.id,
      }),
    onSuccess: (r) => setQueryId(r.id),
  });
  const polled = usePolledQuery(queryId);
  const result = polled.data;
  const running = run.isPending || (result ? QUERY_ACTIVE(result.status) : false);
  const baseSql = `SELECT * FROM ${t.schema_name}.${t.table_name}`;
  const lp = t.latest_partition;

  function exportCsv() {
    if (!result) return;
    const cols = result.columns.map((c) => c.name);
    const esc = (v: unknown) => { const s = v == null ? "" : String(v); return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
    const csv = [cols.join(","), ...result.rows.map((r) => cols.map((c) => esc(r[c])).join(","))].join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    const a = document.createElement("a"); a.href = url; a.download = `${t.table_name}_amostra.csv`; a.click(); URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-gray-500">
        Carregue uma amostra limitada dos dados para validar rapidamente o conteúdo desta tabela.
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <PrimaryButton
          icon={running ? <Loader2 size={15} className="animate-spin" /> : <PlayCircle size={15} />}
          disabled={running}
          onClick={() => run.mutate(baseSql)}
        >
          {running ? "Carregando…" : "Carregar amostra"}
        </PrimaryButton>
        {lp && (
          <SecondaryButton disabled={running} onClick={() => run.mutate(`${baseSql} WHERE ${partitionWhere(lp.path)}`)}>
            Carregar última partição
          </SecondaryButton>
        )}
        <select
          value={limit}
          onChange={(e) => setLimit(Number(e.target.value))}
          className="h-9 rounded-lg border border-gray-200 bg-white px-2 text-sm text-gray-700 focus:outline-none"
        >
          {[10, 50, 100, 500].map((l) => <option key={l} value={l}>{l} linhas</option>)}
        </select>
        {result?.status === "success" && (
          <SecondaryButton onClick={exportCsv}>Exportar CSV</SecondaryButton>
        )}
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
const Empty = ({ text }: { text: string }) => <p className="py-8 text-center text-sm text-gray-400">{text}</p>;
