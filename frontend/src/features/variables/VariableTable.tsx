import { Eye, Pencil, Power, PowerOff, Trash2, Variable as VarIcon } from "lucide-react";

import { DataTable, EmptyState } from "@/components/ui";
import type { Column } from "@/components/ui";
import { cn } from "@/lib/cn";
import { TypeBadge, VariableSecretBadge, VariableStatusBadge } from "@/features/variables/VariableBadges";
import type { Variable } from "@/features/variables/types";
import { fmtDate } from "@/features/variables/types";

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

export function VariableTable({
  rows, loading, perms, onView, onEdit, onToggle, onDelete, pagination,
}: {
  rows: Variable[];
  loading?: boolean;
  perms: Perms;
  onView: (v: Variable) => void;
  onEdit: (v: Variable) => void;
  onToggle: (v: Variable) => void;
  onDelete: (v: Variable) => void;
  pagination?: { page: number; totalPages: number; total: number; hasMore: boolean; onPrev: () => void; onNext: () => void };
}) {
  const columns: Column<Variable>[] = [
    {
      key: "name", header: "Nome",
      render: (v) => (
        <div>
          <div className="font-mono text-sm font-medium text-gray-900">{v.name}</div>
          {v.description && <div className="text-xs text-gray-400">{v.description}</div>}
        </div>
      ),
    },
    { key: "type", header: "Tipo", render: (v) => <TypeBadge type={v.variable_type} /> },
    { key: "scope", header: "Escopo", render: (v) => <span className="text-gray-600">{v.scope}</span> },
    { key: "env", header: "Ambiente", render: (v) => <span className="text-gray-600">{v.environment ?? "—"}</span> },
    {
      key: "value", header: "Valor",
      render: (v) => v.is_secret
        ? <span className="font-mono text-gray-400">********</span>
        : <span className="block max-w-[180px] truncate font-mono text-xs text-gray-600" title={v.value ?? ""}>{v.value ?? "—"}</span>,
    },
    { key: "secret", header: "Secreta", render: (v) => <VariableSecretBadge isSecret={v.is_secret} /> },
    { key: "active", header: "Ativa", render: (v) => <VariableStatusBadge active={v.active} /> },
    { key: "upd", header: "Atualizada em", render: (v) => <span className="text-xs text-gray-500">{fmtDate(v.updated_at ?? v.created_at)}</span> },
    {
      key: "actions", header: "", align: "right",
      render: (v) => (
        <div className="flex items-center justify-end gap-0.5">
          <IconAction title="Ver detalhes" onClick={() => onView(v)}><Eye size={16} /></IconAction>
          {perms.write && <IconAction title="Editar" onClick={() => onEdit(v)}><Pencil size={16} /></IconAction>}
          {perms.write && (v.active
            ? <IconAction title="Inativar" onClick={() => onToggle(v)}><PowerOff size={16} /></IconAction>
            : <IconAction title="Ativar" onClick={() => onToggle(v)}><Power size={16} /></IconAction>)}
          {perms.del && <IconAction title="Remover" danger onClick={() => onDelete(v)}><Trash2 size={16} /></IconAction>}
        </div>
      ),
    },
  ];

  return (
    <DataTable
      columns={columns}
      rows={rows}
      rowKey={(v) => v.id}
      loading={loading}
      onRowClick={onView}
      empty={<EmptyState icon={<VarIcon size={24} />} title="Nenhuma variável cadastrada" description="Cadastre variáveis reutilizáveis para parametrizar jobs e pipelines." />}
      pagination={pagination}
    />
  );
}
