import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Boxes, CheckCircle2, Cloud, Database, FileText, HardDrive, Loader2, Plug, Plus, RefreshCw,
  Table2,
} from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { PageHeader, PrimaryButton, SecondaryButton, EmptyState } from "@/components/ui";
import { Modal } from "@/components/ui/Modal";
import { cn } from "@/lib/cn";
import { DataLakeExplorer } from "@/features/data-lake/DataLakeExplorer";
import { DataLakeTableDetails } from "@/features/data-lake/DataLakeTableDetails";
import { DataLakeQueryConsole } from "@/features/data-lake/DataLakeQueryConsole";
import type { DlConnection, DlScanRun, DlTree, DlTreeCatalog } from "@/features/data-lake/types";
import { QUERY_ACTIVE, catalogHealth, fmtBytes, fmtDate } from "@/features/data-lake/types";

export default function DataLakePage() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const canScan = can("ingest:data-lake:scan");
  const canQuery = can("ingest:data-lake:query");

  const [connId, setConnId] = useState<number | null>(null);
  const [q, setQ] = useState("");
  const [selectedTableId, setSelectedTableId] = useState<number | null>(null);
  const [scanRunId, setScanRunId] = useState<number | null>(null);
  const [consoleOpen, setConsoleOpen] = useState(false);
  // Explorer recolhível: aberto por padrão; recolhe ao selecionar uma tabela; expande no hover.
  const [explorerCollapsed, setExplorerCollapsed] = useState(false);
  const [explorerHovered, setExplorerHovered] = useState(false);
  const [explorerPinned, setExplorerPinned] = useState(false);
  const explorerExpanded = explorerPinned || !explorerCollapsed || explorerHovered;

  function handleSelectTable(id: number) {
    setSelectedTableId(id);
    if (!explorerPinned) {
      setExplorerHovered(false);
      setExplorerCollapsed(true); // libera espaço para o painel de detalhes
    }
  }

  const connections = useQuery({
    queryKey: ["dl-connections"],
    queryFn: () => api.get<DlConnection[]>("/api/v1/data-lake/connections"),
  });

  // Default to the first catalog-enabled connection.
  useEffect(() => {
    if (connId == null && connections.data?.length) {
      const enabled = connections.data.find((c) => c.catalog_enabled) ?? connections.data[0];
      setConnId(enabled.id);
    }
  }, [connections.data, connId]);

  const tree = useQuery({
    queryKey: ["dl-tree"],
    queryFn: () => api.get<DlTree>("/api/v1/data-lake/tree"),
  });

  const currentConn = connections.data?.find((c) => c.id === connId) ?? null;
  const catalog = useMemo(
    () => tree.data?.catalogs.find((c) => c.connection_id === connId) ?? null,
    [tree.data, connId],
  );

  const scan = useMutation({
    mutationFn: (id: number) =>
      api.post<DlScanRun>("/api/v1/data-lake/catalogs/scan", { connection_id: id }),
    onSuccess: (r) => setScanRunId(r.id),
  });

  const [validateMsg, setValidateMsg] = useState<{ ok: boolean; msg: string } | null>(null);
  const validate = useMutation({
    mutationFn: (id: number) => api.post<{ status?: string; message?: string }>(`/api/v1/connections/${id}/test`, {}),
    onSuccess: (r) => setValidateMsg({ ok: r.status === "success", msg: r.message ?? "Teste concluído." }),
    onError: (e) => setValidateMsg({ ok: false, msg: e instanceof ApiError ? e.message : "Falha ao validar." }),
  });

  // Poll the scan run while it's active; refresh the tree when it finishes.
  const scanRun = useQuery({
    queryKey: ["dl-scan-run", scanRunId],
    queryFn: () => api.get<DlScanRun>(`/api/v1/data-lake/scan-runs/${scanRunId}`),
    enabled: scanRunId != null,
    refetchInterval: (query) => (QUERY_ACTIVE(query.state.data?.status ?? "queued") ? 2000 : false),
  });
  useEffect(() => {
    if (scanRun.data && !QUERY_ACTIVE(scanRun.data.status)) {
      qc.invalidateQueries({ queryKey: ["dl-tree"] });
    }
  }, [scanRun.data?.status]);

  const scanning = scan.isPending || (scanRun.data ? QUERY_ACTIVE(scanRun.data.status) : false);

  const noConnections = connections.isFetched && (connections.data?.length ?? 0) === 0;

  return (
    <div>
      <PageHeader
        icon={<Boxes size={22} />}
        title="Data Lake"
        description="Explore buckets, camadas, tabelas, arquivos e dados do Data Lake AWS S3."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            {connId != null && (
              <SecondaryButton
                icon={validate.isPending ? <Loader2 size={16} className="animate-spin" /> : <Plug size={16} />}
                disabled={validate.isPending}
                onClick={() => { setValidateMsg(null); validate.mutate(connId); }}
              >
                Validar conexão
              </SecondaryButton>
            )}
            {canScan && connId != null && (
              <SecondaryButton
                icon={scanning ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
                disabled={scanning}
                onClick={() => scan.mutate(connId)}
              >
                {scanning ? "Atualizando catálogo…" : "Atualizar catálogo"}
              </SecondaryButton>
            )}
            {canQuery && connId != null && (
              <PrimaryButton icon={<Plus size={16} />} onClick={() => setConsoleOpen(true)}>
                Nova consulta
              </PrimaryButton>
            )}
          </div>
        }
      />

      {noConnections ? (
        <div className="mt-6">
          <EmptyState
            icon={<Cloud size={24} />}
            title="Nenhuma conexão S3 configurada"
            description="Cadastre uma conexão AWS S3 / Data Lake para explorar os dados."
          />
        </div>
      ) : (
        <>
          {/* Filtros */}
          <div className="mt-6 flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-2">
              <Cloud size={16} className="text-gray-400" />
              <select
                className="h-10 rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-700 focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
                value={connId ?? ""}
                onChange={(e) => {
                  setConnId(Number(e.target.value));
                  setSelectedTableId(null);
                }}
              >
                {(connections.data ?? []).map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} {c.catalog_enabled ? "" : "(catálogo desativado)"}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {validateMsg && (
            <p className={cn("mt-3 rounded-lg px-3 py-2 text-sm", validateMsg.ok ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700")}>
              {validateMsg.msg}
            </p>
          )}

          <DataLakeSummary catalog={catalog} />

          {currentConn && !currentConn.catalog_enabled && (
            <p className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-700">
              O catálogo não está habilitado nesta conexão. Ative <span className="font-mono text-xs">catalog_enabled</span> nos
              parâmetros da conexão S3 e execute uma varredura.
            </p>
          )}
          {scanRun.data?.status === "failed" && (
            <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
              Falha na varredura: {scanRun.data.error_message}
            </p>
          )}

          <div className="mt-4 flex items-start gap-4">
            <aside
              onMouseEnter={() => setExplorerHovered(true)}
              onMouseLeave={() => setExplorerHovered(false)}
              className={cn(
                "shrink-0 transition-[width] duration-200 ease-in-out",
                explorerExpanded ? "w-[300px]" : "w-16"
              )}
            >
              <DataLakeExplorer
                expanded={explorerExpanded}
                catalog={catalog}
                loading={tree.isLoading}
                filter={q}
                onFilterChange={setQ}
                selectedTableId={selectedTableId}
                onSelectTable={handleSelectTable}
                scanned={!!catalog}
                canScan={canScan}
                onScan={() => connId != null && scan.mutate(connId)}
                pinned={explorerPinned}
                onTogglePin={() => setExplorerPinned((p) => !p)}
              />
            </aside>
            <div className="min-w-0 flex-1">
              {selectedTableId ? (
                <DataLakeTableDetails tableId={selectedTableId} canQuery={canQuery} />
              ) : (
                <div className="rounded-2xl border border-gray-100 bg-white p-10">
                  <EmptyState
                    icon={<Boxes size={24} />}
                    title="Selecione uma tabela"
                    description="Escolha uma tabela no explorer à esquerda para ver resumo, colunas, dados, partições e arquivos."
                  />
                </div>
              )}
            </div>
          </div>
        </>
      )}

      <Modal
        open={consoleOpen}
        onClose={() => setConsoleOpen(false)}
        title="Consulta rápida"
        description="Execução read-only via Spark, com limite automático."
        width="max-w-4xl"
      >
        {connId != null && <DataLakeQueryConsole connectionId={connId} />}
      </Modal>
    </div>
  );
}

function SummaryCard({ icon, label, value }: { icon: React.ReactNode; label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-gray-100 bg-white p-4">
      <div className="flex items-center gap-2 text-gray-400">{icon}<span className="text-xs font-medium uppercase tracking-wide">{label}</span></div>
      <div className="mt-1.5 text-xl font-semibold tabular-nums text-gray-900">{value}</div>
    </div>
  );
}

function DataLakeSummary({ catalog }: { catalog: DlTreeCatalog | null }) {
  const stats = useMemo(() => {
    const schemas = catalog?.schemas ?? [];
    const tables = schemas.flatMap((s) => s.tables);
    return {
      tables: tables.length,
      camadas: schemas.length,
      arquivos: tables.reduce((a, t) => a + (t.files_count ?? 0), 0),
      bytes: tables.reduce((a, t) => a + (t.total_size_bytes ?? 0), 0),
      perLayer: schemas.map((s) => ({ name: s.name, count: s.tables.length })),
    };
  }, [catalog]);
  const health = catalogHealth(catalog?.last_scan_status, catalog?.last_scan_at);

  if (!catalog) return null;
  return (
    <div className="mt-4 space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <span className={cn("inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1", health.cls)}>
          <CheckCircle2 size={13} /> {health.label}
        </span>
        <span className="text-xs text-gray-400">Última varredura: {fmtDate(catalog.last_scan_at)}</span>
        {stats.perLayer.length > 0 && (
          <span className="flex flex-wrap gap-1.5">
            {stats.perLayer.map((l) => (
              <span key={l.name} className="rounded-md bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
                {l.name}: <span className="font-semibold">{l.count}</span>
              </span>
            ))}
          </span>
        )}
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <SummaryCard icon={<Table2 size={16} />} label="Tabelas" value={stats.tables} />
        <SummaryCard icon={<Database size={16} />} label="Camadas" value={stats.camadas} />
        <SummaryCard icon={<FileText size={16} />} label="Arquivos" value={stats.arquivos} />
        <SummaryCard icon={<HardDrive size={16} />} label="Tamanho total" value={fmtBytes(stats.bytes)} />
      </div>
    </div>
  );
}
