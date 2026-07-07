import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CalendarClock, Plus, Search } from "lucide-react";

import { api } from "@/lib/api";
import type { Page } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { PageHeader, PrimaryButton, SecondaryButton } from "@/components/ui";
import { Modal } from "@/components/ui/Modal";
import { ScheduleSummaryCards } from "@/features/schedules/ScheduleSummaryCards";
import { ScheduleTable } from "@/features/schedules/ScheduleTable";
import { ScheduleForm } from "@/features/schedules/ScheduleForm";
import type { SchedulePayload } from "@/features/schedules/ScheduleForm";
import { ScheduleRunsModal } from "@/features/schedules/ScheduleRunsModal";
import { useScheduleActions } from "@/features/schedules/useScheduleActions";
import type { Schedule, ScheduleSummary } from "@/features/schedules/types";

const selectCls =
  "h-10 rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-700 focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-500/20";

export default function SchedulesPage() {
  const { can } = useAuth();
  const actions = useScheduleActions();

  const [active, setActive] = useState("");
  const [type, setType] = useState("");
  const [lastStatus, setLastStatus] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Schedule | null>(null);
  const [runsFor, setRunsFor] = useState<Schedule | null>(null);
  const [deleting, setDeleting] = useState<Schedule | null>(null);

  const perms = {
    write: can("ingest:schedules:write"),
    del: can("ingest:schedules:delete"),
    enable: can("ingest:schedules:enable"),
    disable: can("ingest:schedules:disable"),
    run: can("ingest:schedules:run"),
  };

  const query = useMemo(() => {
    const p = new URLSearchParams({ page: String(page), page_size: "25" });
    if (active) p.set("active", active);
    if (type) p.set("schedule_type", type);
    if (lastStatus) p.set("last_status", lastStatus);
    if (q.trim()) p.set("q", q.trim());
    return p.toString();
  }, [active, type, lastStatus, q, page]);

  const summary = useQuery({ queryKey: ["schedules-summary"], queryFn: () => api.get<ScheduleSummary>("/api/v1/job-schedules/summary") });
  const list = useQuery({ queryKey: ["schedules", query], queryFn: () => api.get<Page<Schedule>>(`/api/v1/job-schedules?${query}`) });
  const jobs = useQuery({
    queryKey: ["jobs-min"],
    queryFn: () => api.get<Page<{ id: number; name: string }>>("/api/v1/jobs?page=1&page_size=200"),
    enabled: formOpen && !editing,
  });

  async function handleSubmit(payload: SchedulePayload) {
    if (editing) await actions.update.mutateAsync({ id: editing.id, payload });
    else await actions.create.mutateAsync({ payload });
    setFormOpen(false);
  }

  return (
    <div>
      <PageHeader
        icon={<CalendarClock size={22} />}
        title="Schedules"
        description="Gerencie os agendamentos automáticos de execução dos jobs."
        actions={perms.write ? <PrimaryButton icon={<Plus size={16} />} onClick={() => { setEditing(null); setFormOpen(true); }}>Novo schedule</PrimaryButton> : null}
      />

      <ScheduleSummaryCards summary={summary.data} loading={summary.isLoading} />

      <div className="mt-6 flex flex-wrap items-center gap-2">
        <div className="relative min-w-[200px] flex-1">
          <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input value={q} onChange={(e) => { setPage(1); setQ(e.target.value); }} placeholder="Buscar por nome…" className="h-10 w-full rounded-lg border border-gray-200 bg-white pl-9 pr-3 text-sm text-gray-700 focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-500/20" />
        </div>
        <select className={selectCls} value={type} onChange={(e) => { setPage(1); setType(e.target.value); }}>
          <option value="">Todos os tipos</option>
          {["cron", "hourly", "daily", "weekly", "monthly", "manual"].map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <select className={selectCls} value={active} onChange={(e) => { setPage(1); setActive(e.target.value); }}>
          <option value="">Ativos e inativos</option>
          <option value="true">Somente ativos</option>
          <option value="false">Somente inativos</option>
        </select>
        <select className={selectCls} value={lastStatus} onChange={(e) => { setPage(1); setLastStatus(e.target.value); }}>
          <option value="">Qualquer status</option>
          <option value="success">Sucesso</option>
          <option value="failed">Erro</option>
          <option value="queued">Na fila</option>
        </select>
      </div>

      <div className="mt-4">
        <ScheduleTable
          rows={list.data?.items ?? []}
          loading={list.isLoading}
          perms={perms}
          busyId={actions.toggle.variables?.id ?? actions.run.variables?.id ?? null}
          onEdit={(s) => { setEditing(s); setFormOpen(true); }}
          onToggle={(s) => actions.toggle.mutate(s)}
          onRun={(s) => actions.run.mutate(s)}
          onRuns={setRunsFor}
          onDelete={setDeleting}
          pagination={
            list.data
              ? { page: list.data.page, totalPages: list.data.total_pages, total: list.data.total, hasMore: list.data.has_more, onPrev: () => setPage((p) => Math.max(1, p - 1)), onNext: () => setPage((p) => p + 1) }
              : undefined
          }
        />
      </div>

      <Modal open={formOpen} onClose={() => setFormOpen(false)} title={editing ? "Editar schedule" : "Novo schedule"} description="Configure o agendamento automático do job." width="max-w-2xl">
        <ScheduleForm
          initial={editing}
          jobs={jobs.data?.items}
          saving={actions.create.isPending || actions.update.isPending}
          onSubmit={handleSubmit}
          onCancel={() => setFormOpen(false)}
        />
      </Modal>

      <ScheduleRunsModal schedule={runsFor} onClose={() => setRunsFor(null)} />

      <Modal
        open={!!deleting}
        onClose={() => setDeleting(null)}
        title="Remover schedule"
        footer={
          <>
            <SecondaryButton onClick={() => setDeleting(null)}>Cancelar</SecondaryButton>
            <PrimaryButton className="bg-red-600 hover:bg-red-700" loading={actions.remove.isPending} onClick={async () => { if (deleting) { await actions.remove.mutateAsync(deleting.id); setDeleting(null); } }}>
              Remover
            </PrimaryButton>
          </>
        }
      >
        <p className="text-sm text-gray-600">Remover o agendamento <span className="font-semibold text-gray-900">{deleting?.name}</span>? Esta ação não pode ser desfeita.</p>
      </Modal>
    </div>
  );
}
