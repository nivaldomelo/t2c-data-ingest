import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Boxes, Cloud, Loader2, Plus, RefreshCw, Search } from "lucide-react";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { PageHeader, PrimaryButton, SecondaryButton, EmptyState } from "@/components/ui";
import { Modal } from "@/components/ui/Modal";
import { DataLakeExplorer } from "@/features/data-lake/DataLakeExplorer";
import { DataLakeTableDetails } from "@/features/data-lake/DataLakeTableDetails";
import { DataLakeQueryConsole } from "@/features/data-lake/DataLakeQueryConsole";
import type { DlConnection, DlScanRun, DlTree } from "@/features/data-lake/types";
import { QUERY_ACTIVE } from "@/features/data-lake/types";

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
            {canScan && connId != null && (
              <SecondaryButton
                icon={scanning ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
                disabled={scanning}
                onClick={() => scan.mutate(connId)}
              >
                {scanning ? "Atualizando…" : "Atualizar catálogo"}
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
            <div className="relative min-w-[220px] flex-1">
              <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Buscar tabela…"
                className="h-10 w-full rounded-lg border border-gray-200 bg-white pl-9 pr-3 text-sm text-gray-700 placeholder:text-gray-400 focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
              />
            </div>
          </div>

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

          <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-[320px_1fr]">
            <DataLakeExplorer
              catalog={catalog}
              loading={tree.isLoading}
              filter={q}
              selectedTableId={selectedTableId}
              onSelectTable={setSelectedTableId}
              scanned={!!catalog}
              canScan={canScan}
              onScan={() => connId != null && scan.mutate(connId)}
            />
            <div className="min-w-0">
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
