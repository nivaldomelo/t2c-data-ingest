import { Link } from "react-router-dom";
import { History, Pencil, Play, Power, PowerOff, Trash2 } from "lucide-react";

import { DataTable, EmptyState, StatusBadge } from "@/components/ui";
import type { Column } from "@/components/ui";
import { cn } from "@/lib/cn";
import { CalendarClock } from "lucide-react";
import type { Schedule } from "@/features/schedules/types";
import { fmtDateTime } from "@/features/schedules/types";

interface Perms {
  write: boolean;
  del: boolean;
  enable: boolean;
  disable: boolean;
  run: boolean;
}

interface Props {
  rows: Schedule[];
  loading?: boolean;
  perms: Perms;
  showJob?: boolean;
  busyId?: number | null;
  onEdit: (s: Schedule) => void;
  onToggle: (s: Schedule) => void;
  onRun: (s: Schedule) => void;
  onRuns: (s: Schedule) => void;
  onDelete: (s: Schedule) => void;
  pagination?: {
    page: number; totalPages: number; total: number; hasMore: boolean;
    onPrev: () => void; onNext: () => void;
  };
}

function IconAction({ title, onClick, children, danger }: { title: string; onClick: () => void; children: React.ReactNode; danger?: boolean }) {
  return (
    <button
      title={title}
      onClick={(e) => { e.stopPropagation(); onClick(); }}
      className={cn(
        "inline-flex h-8 w-8 items-center justify-center rounded-lg text-gray-400 transition-colors",
        danger ? "hover:bg-red-50 hover:text-red-600" : "hover:bg-gray-100 hover:text-gray-700"
      )}
    >
      {children}
    </button>
  );
}

export function ScheduleTable({ rows, loading, perms, showJob = true, onEdit, onToggle, onRun, onRuns, onDelete, pagination }: Props) {
  const columns: Column<Schedule>[] = [
    {
      key: "name",
      header: "Nome",
      render: (s) => (
        <div>
          <div className="font-medium text-gray-900">{s.name}</div>
          {s.description && <div className="text-xs text-gray-400">{s.description}</div>}
        </div>
      ),
    },
    ...(showJob
      ? [{
          key: "job",
          header: "Job",
          render: (s: Schedule) => (
            <Link to={`/jobs/${s.job_id}`} onClick={(e) => e.stopPropagation()} className="text-gray-600 hover:text-brand-600 hover:underline">
              {s.job_name ?? `#${s.job_id}`}
            </Link>
          ),
        } as Column<Schedule>]
      : []),
    { key: "type", header: "Tipo", render: (s) => <span className="inline-flex rounded-md bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600">{s.schedule_type}</span> },
    { key: "cron", header: "Expressão", render: (s) => <span className="font-mono text-xs text-gray-600">{s.cron_expression ?? "—"}</span> },
    { key: "tz", header: "Timezone", render: (s) => <span className="text-xs text-gray-500">{s.timezone}</span> },
    { key: "next", header: "Próxima", render: (s) => <span className={cn("text-xs", s.next_run_at ? "font-medium text-brand-600" : "text-gray-400")}>{fmtDateTime(s.next_run_at)}</span> },
    { key: "last", header: "Última", render: (s) => <span className="text-xs text-gray-500">{fmtDateTime(s.last_run_at)}</span> },
    { key: "status", header: "Último status", render: (s) => (s.last_status ? <StatusBadge status={s.last_status} /> : <span className="text-xs text-gray-400">—</span>) },
    { key: "active", header: "Ativo", render: (s) => <StatusBadge status={s.active ? "active" : "inactive"} /> },
    {
      key: "actions",
      header: "",
      align: "right",
      render: (s) => (
        <div className="flex items-center justify-end gap-0.5">
          {perms.run && <IconAction title="Executar agora" onClick={() => onRun(s)}><Play size={16} /></IconAction>}
          <IconAction title="Ver execuções" onClick={() => onRuns(s)}><History size={16} /></IconAction>
          {perms.write && <IconAction title="Editar" onClick={() => onEdit(s)}><Pencil size={16} /></IconAction>}
          {(perms.enable && !s.active) && <IconAction title="Ativar" onClick={() => onToggle(s)}><Power size={16} /></IconAction>}
          {(perms.disable && s.active) && <IconAction title="Inativar" onClick={() => onToggle(s)}><PowerOff size={16} /></IconAction>}
          {perms.del && <IconAction title="Remover" danger onClick={() => onDelete(s)}><Trash2 size={16} /></IconAction>}
        </div>
      ),
    },
  ];

  return (
    <DataTable
      columns={columns}
      rows={rows}
      rowKey={(s) => s.id}
      loading={loading}
      onRowClick={onRuns}
      empty={<EmptyState icon={<CalendarClock size={24} />} title="Nenhum agendamento" description="Crie um agendamento para executar o job automaticamente." />}
      pagination={pagination}
    />
  );
}
