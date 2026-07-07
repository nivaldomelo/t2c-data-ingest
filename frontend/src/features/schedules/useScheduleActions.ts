import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { Schedule } from "@/features/schedules/types";
import type { SchedulePayload } from "@/features/schedules/ScheduleForm";

export function useScheduleActions() {
  const qc = useQueryClient();
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["schedules"] });
    qc.invalidateQueries({ queryKey: ["schedules-summary"] });
    qc.invalidateQueries({ queryKey: ["job-schedules"] });
  };

  const create = useMutation({
    mutationFn: (p: { payload: SchedulePayload; jobId?: number }) =>
      p.jobId
        ? api.post<Schedule>(`/api/v1/jobs/${p.jobId}/schedules`, p.payload)
        : api.post<Schedule>("/api/v1/job-schedules", p.payload),
    onSuccess: invalidate,
  });
  const update = useMutation({
    mutationFn: (p: { id: number; payload: SchedulePayload }) =>
      api.put<Schedule>(`/api/v1/job-schedules/${p.id}`, p.payload),
    onSuccess: invalidate,
  });
  const toggle = useMutation({
    mutationFn: (s: Schedule) =>
      api.post<Schedule>(`/api/v1/job-schedules/${s.id}/${s.active ? "disable" : "enable"}`, {}),
    onSuccess: invalidate,
  });
  const run = useMutation({
    mutationFn: (s: Schedule) => api.post(`/api/v1/job-schedules/${s.id}/run`, {}),
    onSuccess: invalidate,
  });
  const remove = useMutation({
    mutationFn: (id: number) => api.del(`/api/v1/job-schedules/${id}`),
    onSuccess: invalidate,
  });

  return { create, update, toggle, run, remove };
}
