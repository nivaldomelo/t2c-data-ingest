import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";

import { api } from "@/lib/api";
import type { Page } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { PrimaryButton, SecondaryButton } from "@/components/ui";
import { Modal } from "@/components/ui/Modal";
import { ScheduleTable } from "@/features/schedules/ScheduleTable";
import { ScheduleForm } from "@/features/schedules/ScheduleForm";
import type { SchedulePayload } from "@/features/schedules/ScheduleForm";
import { ScheduleRunsModal } from "@/features/schedules/ScheduleRunsModal";
import { useScheduleActions } from "@/features/schedules/useScheduleActions";
import type { Schedule } from "@/features/schedules/types";

export function JobSchedulesTab({ jobId }: { jobId: number }) {
  const { can } = useAuth();
  const actions = useScheduleActions();
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

  const { data, isLoading } = useQuery({
    queryKey: ["job-schedules", jobId],
    queryFn: () => api.get<Page<Schedule>>(`/api/v1/jobs/${jobId}/schedules?page=1&page_size=25`),
  });

  async function handleSubmit(payload: SchedulePayload) {
    if (editing) await actions.update.mutateAsync({ id: editing.id, payload });
    else await actions.create.mutateAsync({ payload, jobId });
    setFormOpen(false);
  }

  return (
    <div>
      <div className="mb-4 flex justify-end">
        {perms.write && (
          <PrimaryButton icon={<Plus size={16} />} onClick={() => { setEditing(null); setFormOpen(true); }}>
            Novo agendamento
          </PrimaryButton>
        )}
      </div>

      <ScheduleTable
        rows={data?.items ?? []}
        loading={isLoading}
        perms={perms}
        showJob={false}
        onEdit={(s) => { setEditing(s); setFormOpen(true); }}
        onToggle={(s) => actions.toggle.mutate(s)}
        onRun={(s) => actions.run.mutate(s)}
        onRuns={setRunsFor}
        onDelete={setDeleting}
      />

      <Modal open={formOpen} onClose={() => setFormOpen(false)} title={editing ? "Editar agendamento" : "Novo agendamento"} width="max-w-2xl">
        <ScheduleForm
          initial={editing}
          fixedJobId={jobId}
          saving={actions.create.isPending || actions.update.isPending}
          onSubmit={handleSubmit}
          onCancel={() => setFormOpen(false)}
        />
      </Modal>

      <ScheduleRunsModal schedule={runsFor} onClose={() => setRunsFor(null)} />

      <Modal
        open={!!deleting}
        onClose={() => setDeleting(null)}
        title="Remover agendamento"
        footer={
          <>
            <SecondaryButton onClick={() => setDeleting(null)}>Cancelar</SecondaryButton>
            <PrimaryButton className="bg-red-600 hover:bg-red-700" loading={actions.remove.isPending} onClick={async () => { if (deleting) { await actions.remove.mutateAsync(deleting.id); setDeleting(null); } }}>
              Remover
            </PrimaryButton>
          </>
        }
      >
        <p className="text-sm text-gray-600">Remover o agendamento <span className="font-semibold text-gray-900">{deleting?.name}</span>?</p>
      </Modal>
    </div>
  );
}
