import { Eye, Loader2, Pencil, PlugZap, Trash2 } from "lucide-react";

import { DataTable, EmptyState, StatusBadge } from "@/components/ui";
import type { Column } from "@/components/ui";
import { Plug } from "lucide-react";
import { cn } from "@/lib/cn";
import { ConnectionStatusBadge } from "@/features/connections/ConnectionStatusBadge";
import type { Connection } from "@/features/connections/types";
import { CATEGORY_LABEL, typeLabel } from "@/features/connections/types";

function endpointOf(c: Connection): string {
  const ep = (c.extra_params ?? {}) as Record<string, unknown>;
  if (c.connection_category === "storage") return String(ep.bucket_name ?? "—");
  if (c.connection_category === "api") return String(ep.base_url ?? "—");
  return c.host ? `${c.host}${c.port ? `:${c.port}` : ""}` : "—";
}

function RwChips({ c }: { c: Connection }) {
  return (
    <span className="ml-1.5 inline-flex gap-1 align-middle">
      {c.can_read && (
        <span className="rounded bg-sky-50 px-1.5 py-0.5 text-[10px] font-semibold text-sky-700">R</span>
      )}
      {c.can_write && (
        <span className="rounded bg-amber-50 px-1.5 py-0.5 text-[10px] font-semibold text-amber-700">W</span>
      )}
    </span>
  );
}

interface Perms {
  write: boolean;
  test: boolean;
  del: boolean;
}

interface Props {
  rows: Connection[];
  loading?: boolean;
  perms: Perms;
  testingId?: number | null;
  onView: (c: Connection) => void;
  onEdit: (c: Connection) => void;
  onTest: (c: Connection) => void;
  onDelete: (c: Connection) => void;
}

function IconAction({
  title,
  onClick,
  children,
  danger,
}: {
  title: string;
  onClick: () => void;
  children: React.ReactNode;
  danger?: boolean;
}) {
  return (
    <button
      title={title}
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      className={cn(
        "inline-flex h-8 w-8 items-center justify-center rounded-lg text-gray-400 transition-colors",
        danger ? "hover:bg-red-50 hover:text-red-600" : "hover:bg-gray-100 hover:text-gray-700"
      )}
    >
      {children}
    </button>
  );
}

export function ConnectionTable({
  rows,
  loading,
  perms,
  testingId,
  onView,
  onEdit,
  onTest,
  onDelete,
}: Props) {
  const columns: Column<Connection>[] = [
    {
      key: "name",
      header: "Nome",
      render: (c) => (
        <div>
          <div className="font-medium text-gray-900">{c.name}</div>
          {c.description && <div className="text-xs text-gray-400">{c.description}</div>}
        </div>
      ),
    },
    {
      key: "category",
      header: "Categoria",
      render: (c) => (
        <span className="text-xs text-gray-500">{CATEGORY_LABEL[c.connection_category ?? "database"]}</span>
      ),
    },
    {
      key: "type",
      header: "Tipo",
      render: (c) => (
        <span className="whitespace-nowrap">
          <span className="inline-flex rounded-md bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600">
            {typeLabel(c.connection_type)}
          </span>
          <RwChips c={c} />
        </span>
      ),
    },
    {
      key: "endpoint",
      header: "Host / Bucket / URL",
      render: (c) => <span className="font-mono text-xs text-gray-600">{endpointOf(c)}</span>,
    },
    { key: "test", header: "Último teste", render: (c) => <ConnectionStatusBadge status={c.last_test_status} /> },
    {
      key: "tested_at",
      header: "Testado em",
      render: (c) => (
        <span className="text-xs text-gray-400">
          {c.last_tested_at ? new Date(c.last_tested_at).toLocaleString("pt-BR") : "—"}
        </span>
      ),
    },
    { key: "active", header: "Ativo", render: (c) => <StatusBadge status={c.active ? "active" : "inactive"} /> },
    {
      key: "actions",
      header: "",
      align: "right",
      render: (c) => (
        <div className="flex items-center justify-end gap-0.5">
          <IconAction title="Ver detalhes" onClick={() => onView(c)}>
            <Eye size={16} />
          </IconAction>
          {perms.test && (
            <IconAction title="Testar origem" onClick={() => onTest(c)}>
              {testingId === c.id ? <Loader2 size={16} className="animate-spin text-brand-500" /> : <PlugZap size={16} />}
            </IconAction>
          )}
          {perms.write && (
            <IconAction title="Editar" onClick={() => onEdit(c)}>
              <Pencil size={16} />
            </IconAction>
          )}
          {perms.del && (
            <IconAction title="Remover" danger onClick={() => onDelete(c)}>
              <Trash2 size={16} />
            </IconAction>
          )}
        </div>
      ),
    },
  ];

  return (
    <DataTable
      columns={columns}
      rows={rows}
      rowKey={(c) => c.id}
      loading={loading}
      onRowClick={onView}
      empty={
        <EmptyState
          icon={<Plug size={24} />}
          title="Nenhuma origem cadastrada"
          description="Cadastre uma conexão PostgreSQL, MySQL ou AWS S3 / Data Lake para usar em jobs e pipelines."
        />
      }
    />
  );
}
