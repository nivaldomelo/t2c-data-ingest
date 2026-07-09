import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Boxes, PackagePlus, RefreshCw, Trash2 } from "lucide-react";

import { api, type Page } from "@/lib/api";
import { Card, DataTable, EmptyState, PageHeader, PrimaryButton } from "@/components/ui";
import type { Column } from "@/components/ui";
import { useAuth } from "@/lib/auth";
import { LibraryStatusBadge } from "@/features/libraries/LibraryStatusBadge";
import { LibraryInstallModal } from "@/features/libraries/LibraryInstallModal";
import { LibraryDetailDrawer } from "@/features/libraries/LibraryDetailDrawer";
import type { Library, LibrarySummary } from "@/features/libraries/types";

function fmt(t: string | null): string {
  return t ? new Date(t).toLocaleString("pt-BR") : "—";
}

function MetricCard({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <Card className="p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-gray-400">{label}</p>
      <div className="mt-2 text-2xl font-bold text-gray-900">{value}</div>
    </Card>
  );
}

export default function LibrariesPage() {
  const { can } = useAuth();
  const canInstall = can("ingest:libraries:install");
  const canUninstall = can("ingest:libraries:uninstall");
  const [installOpen, setInstallOpen] = useState(false);
  const [detailId, setDetailId] = useState<number | null>(null);

  const { data: summary } = useQuery({
    queryKey: ["libraries-summary"],
    queryFn: () => api.get<LibrarySummary>("/api/v1/libraries/summary"),
    refetchInterval: (q) => ((q.state.data as LibrarySummary | undefined)?.running ? 4000 : false),
  });

  const { data, isLoading } = useQuery({
    queryKey: ["libraries"],
    queryFn: () => api.get<Page<Library>>("/api/v1/libraries?page=1&page_size=200"),
    refetchInterval: (q) => {
      const rows = (q.state.data as Page<Library> | undefined)?.items ?? [];
      return rows.some((r) => ["queued", "installing"].includes(r.status)) ? 3000 : false;
    },
  });
  const rows = data?.items ?? [];

  const columns: Column<Library>[] = [
    { key: "package", header: "Pacote", render: (r) => <span className="font-medium text-gray-900">{r.package_name}</span> },
    { key: "version", header: "Versão", render: (r) => <span className="font-mono text-xs text-gray-600">{r.package_version ?? "—"}</span> },
    { key: "source", header: "Origem", render: (r) => <span className="text-xs uppercase text-gray-500">{r.source}</span> },
    { key: "scope", header: "Escopo", render: (r) => <span className="text-xs text-gray-500">{r.install_scope}</span> },
    { key: "status", header: "Status", render: (r) => <LibraryStatusBadge status={r.status} /> },
    { key: "installed_at", header: "Instalado em", render: (r) => <span className="text-xs text-gray-500">{fmt(r.installed_at)}</span> },
    { key: "installed_by", header: "Instalado por", render: (r) => <span className="text-xs text-gray-500">{r.installed_by ?? "—"}</span> },
    {
      key: "actions", header: "Ações", align: "right",
      render: (r) => (
        <div className="flex justify-end gap-1.5" onClick={(e) => e.stopPropagation()}>
          <button onClick={() => setDetailId(r.id)} className="rounded-md border border-gray-200 bg-white px-2.5 py-1 text-xs font-medium text-gray-600 hover:bg-gray-50">Detalhes</button>
          {canUninstall && r.status !== "removed" && (
            <button onClick={() => setDetailId(r.id)} title="Remover / reinstalar no detalhe" className="rounded-md border border-gray-200 bg-white p-1.5 text-gray-500 hover:bg-gray-50">
              {r.status === "failed" ? <RefreshCw size={13} /> : <Trash2 size={13} />}
            </button>
          )}
        </div>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        icon={<Boxes size={22} />}
        title="Bibliotecas"
        description="Instale e gerencie dependências Python usadas por jobs Spark e Python."
        actions={canInstall && (
          <PrimaryButton icon={<PackagePlus size={16} />} onClick={() => setInstallOpen(true)}>Instalar biblioteca</PrimaryButton>
        )}
      />

      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-5">
        <MetricCard label="Bibliotecas instaladas" value={summary?.installed ?? "—"} />
        <MetricCard label="Com sucesso" value={summary?.success ?? "—"} />
        <MetricCard label="Com erro" value={<span className={summary?.failed ? "text-red-600" : undefined}>{summary?.failed ?? "—"}</span>} />
        <MetricCard label="Em andamento" value={<span className={summary?.running ? "text-brand-600" : undefined}>{summary?.running ?? "—"}</span>} />
        <MetricCard label="Última instalação" value={<span className="text-sm font-medium">{summary?.last_installed_at ? fmt(summary.last_installed_at) : "—"}</span>} />
      </div>

      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(r) => r.id}
        loading={isLoading}
        onRowClick={(r) => setDetailId(r.id)}
        empty={<EmptyState icon={<Boxes size={24} />} title="Nenhuma biblioteca" description="Instale a primeira biblioteca Python para seus jobs Spark/Python." />}
      />

      <LibraryInstallModal open={installOpen} onClose={() => setInstallOpen(false)} />
      <LibraryDetailDrawer
        libraryId={detailId}
        open={detailId != null}
        onClose={() => setDetailId(null)}
        canInstall={canInstall}
        canUninstall={canUninstall}
      />
    </div>
  );
}
