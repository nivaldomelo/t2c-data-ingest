import { Eye, Pencil, Power, PowerOff, Trash2 } from "lucide-react";
import { Database } from "lucide-react";

import { DataTable, EmptyState } from "@/components/ui";
import type { Column } from "@/components/ui";
import { cn } from "@/lib/cn";
import { AtivoBadge, IngestionControlStatusBadge } from "@/features/ingestion-control/IngestionControlStatusBadge";
import type { IngestionControl } from "@/features/ingestion-control/types";
import { fmtDate } from "@/features/ingestion-control/types";

interface Perms { write: boolean; del: boolean }

function IconAction({ title, onClick, children, danger }: { title: string; onClick: () => void; children: React.ReactNode; danger?: boolean }) {
  return (
    <button title={title} onClick={(e) => { e.stopPropagation(); onClick(); }}
      className={cn("inline-flex h-8 w-8 items-center justify-center rounded-lg text-gray-400 transition-colors",
        danger ? "hover:bg-red-50 hover:text-red-600" : "hover:bg-gray-100 hover:text-gray-700")}>
      {children}
    </button>
  );
}

export function IngestionControlTable({
  rows, loading, perms, onView, onEdit, onToggle, onDelete, pagination,
}: {
  rows: IngestionControl[];
  loading?: boolean;
  perms: Perms;
  onView: (r: IngestionControl) => void;
  onEdit: (r: IngestionControl) => void;
  onToggle: (r: IngestionControl) => void;
  onDelete: (r: IngestionControl) => void;
  pagination?: { page: number; totalPages: number; total: number; hasMore: boolean; onPrev: () => void; onNext: () => void };
}) {
  const columns: Column<IngestionControl>[] = [
    { key: "nome", header: "Nome da tabela", render: (r) => <span className="font-medium text-gray-900">{r.nome_tabela}</span> },
    { key: "grupo", header: "Grupo", render: (r) => <span className="text-gray-600">{r.grupo ?? "—"}</span> },
    { key: "tipo", header: "Tipo ingestão", render: (r) => (r.tipo_ingestao ? <span className="inline-flex rounded-md bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600">{r.tipo_ingestao}</span> : "—") },
    { key: "origem", header: "Origem", render: (r) => <span className="text-gray-600">{r.origem ?? "—"}</span> },
    { key: "destino", header: "Destino", render: (r) => <span className="text-gray-600">{r.destino ?? "—"}</span> },
    { key: "wm", header: "Watermark", render: (r) => <span className="text-xs text-gray-500">{fmtDate(r.watermark_atual)}</span> },
    { key: "ult", header: "Última execução", render: (r) => <span className="text-xs text-gray-500">{fmtDate(r.ultima_execucao)}</span> },
    { key: "status", header: "Status", render: (r) => <IngestionControlStatusBadge status={r.status} /> },
    { key: "ativo", header: "Ativo", render: (r) => <AtivoBadge ativo={r.ativo} /> },
    {
      key: "actions", header: "", align: "right",
      render: (r) => (
        <div className="flex items-center justify-end gap-0.5">
          <IconAction title="Ver detalhes" onClick={() => onView(r)}><Eye size={16} /></IconAction>
          {perms.write && <IconAction title="Editar" onClick={() => onEdit(r)}><Pencil size={16} /></IconAction>}
          {perms.write && (r.ativo
            ? <IconAction title="Inativar" onClick={() => onToggle(r)}><PowerOff size={16} /></IconAction>
            : <IconAction title="Ativar" onClick={() => onToggle(r)}><Power size={16} /></IconAction>)}
          {perms.del && <IconAction title="Remover" danger onClick={() => onDelete(r)}><Trash2 size={16} /></IconAction>}
        </div>
      ),
    },
  ];

  return (
    <DataTable
      columns={columns}
      rows={rows}
      rowKey={(r) => r.id}
      loading={loading}
      onRowClick={onView}
      empty={<EmptyState icon={<Database size={24} />} title="Nenhuma tabela cadastrada" description="Cadastre uma tabela de controle para parametrizar as ingestões." />}
      pagination={pagination}
    />
  );
}
