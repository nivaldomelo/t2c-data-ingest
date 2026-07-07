import { useState } from "react";
import type { FormEvent } from "react";
import { CalendarCheck2, CheckCircle2, XCircle } from "lucide-react";

import { api } from "@/lib/api";
import { PrimaryButton, SecondaryButton } from "@/components/ui";
import type { CronValidateResponse, Schedule, ScheduleType } from "@/features/schedules/types";
import { CRON_TEMPLATES, TIMEZONES, fmtDateTime } from "@/features/schedules/types";

export interface SchedulePayload {
  job_id?: number;
  name: string;
  description: string | null;
  schedule_type: ScheduleType;
  cron_expression: string | null;
  timezone: string;
  start_at: string | null;
  end_at: string | null;
  active: boolean;
  parameters: Record<string, unknown> | null;
}

interface JobOption {
  id: number;
  name: string;
}

const label = "block text-sm font-medium text-gray-700";
const field =
  "mt-1.5 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-500/20";

function toLocalInput(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const off = d.getTimezoneOffset();
  return new Date(d.getTime() - off * 60000).toISOString().slice(0, 16);
}

export function ScheduleForm({
  initial,
  fixedJobId,
  jobs,
  saving,
  onSubmit,
  onCancel,
}: {
  initial: Schedule | null;
  fixedJobId?: number;
  jobs?: JobOption[];
  saving?: boolean;
  onSubmit: (payload: SchedulePayload) => void;
  onCancel: () => void;
}) {
  const [jobId, setJobId] = useState<number | "">(fixedJobId ?? initial?.job_id ?? "");
  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [scheduleType, setScheduleType] = useState<ScheduleType>(initial?.schedule_type ?? "cron");
  const [cron, setCron] = useState(initial?.cron_expression ?? "*/15 * * * *");
  const [timezone, setTimezone] = useState(initial?.timezone ?? "America/Sao_Paulo");
  const [startAt, setStartAt] = useState(toLocalInput(initial?.start_at ?? null));
  const [endAt, setEndAt] = useState(toLocalInput(initial?.end_at ?? null));
  const [active, setActive] = useState(initial?.active ?? true);
  const [paramsText, setParamsText] = useState(initial?.parameters ? JSON.stringify(initial.parameters, null, 2) : "");
  const [error, setError] = useState<string | null>(null);
  const [validation, setValidation] = useState<CronValidateResponse | null>(null);
  const [templateLabel, setTemplateLabel] = useState<string>("");

  function applyTemplate(lbl: string) {
    setTemplateLabel(lbl);
    const t = CRON_TEMPLATES.find((x) => x.label === lbl);
    if (t && t.cron) {
      setCron(t.cron);
      setScheduleType(t.type);
      setValidation(null);
    }
  }

  async function validateCron() {
    setValidation(null);
    try {
      const res = await api.post<CronValidateResponse>("/api/v1/job-schedules/validate-cron", {
        cron_expression: cron,
        timezone,
      });
      setValidation(res);
    } catch {
      setValidation({ valid: false, error: "Falha ao validar.", next_runs: [] });
    }
  }

  function build(): SchedulePayload | null {
    let parameters: Record<string, unknown> | null = null;
    if (paramsText.trim()) {
      try {
        parameters = JSON.parse(paramsText);
      } catch {
        setError("Parâmetros devem ser um JSON válido.");
        return null;
      }
    }
    if (scheduleType !== "manual" && !cron.trim()) {
      setError("Informe uma expressão cron ou escolha o tipo manual.");
      return null;
    }
    return {
      ...(fixedJobId ? {} : { job_id: jobId === "" ? undefined : Number(jobId) }),
      name: name.trim(),
      description: description.trim() || null,
      schedule_type: scheduleType,
      cron_expression: scheduleType === "manual" ? null : cron.trim(),
      timezone,
      start_at: startAt ? new Date(startAt).toISOString() : null,
      end_at: endAt ? new Date(endAt).toISOString() : null,
      active,
      parameters,
    };
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!name.trim()) return setError("Informe o nome do agendamento.");
    if (!fixedJobId && !jobId) return setError("Selecione o job.");
    const payload = build();
    if (payload) onSubmit(payload);
  }

  return (
    <form onSubmit={submit}>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {!fixedJobId && (
          <div className="sm:col-span-2">
            <label className={label}>Job *</label>
            <select className={field} value={jobId} onChange={(e) => setJobId(e.target.value ? Number(e.target.value) : "")} disabled={!!initial}>
              <option value="">Selecione um job…</option>
              {(jobs ?? []).map((j) => <option key={j.id} value={j.id}>{j.name}</option>)}
            </select>
          </div>
        )}
        <div className="sm:col-span-2">
          <label className={label}>Nome do agendamento *</label>
          <input className={field} value={name} onChange={(e) => setName(e.target.value)} placeholder="ex.: carga diária clientes" />
        </div>
        <div className="sm:col-span-2">
          <label className={label}>Descrição</label>
          <input className={field} value={description} onChange={(e) => setDescription(e.target.value)} />
        </div>

        <div className="sm:col-span-2">
          <label className={label}>Template rápido</label>
          <select className={field} value={templateLabel} onChange={(e) => applyTemplate(e.target.value)}>
            <option value="">Escolha um template…</option>
            {CRON_TEMPLATES.map((t) => <option key={t.label} value={t.label}>{t.label}</option>)}
          </select>
        </div>

        <div>
          <label className={label}>Tipo</label>
          <select className={field} value={scheduleType} onChange={(e) => setScheduleType(e.target.value as ScheduleType)}>
            {["cron", "hourly", "daily", "weekly", "monthly", "manual"].map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
        <div>
          <label className={label}>Timezone</label>
          <select className={field} value={timezone} onChange={(e) => setTimezone(e.target.value)}>
            {TIMEZONES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>

        {scheduleType !== "manual" && (
          <div className="sm:col-span-2">
            <label className={label}>Expressão cron</label>
            <div className="flex gap-2">
              <input className={`${field} font-mono`} value={cron} onChange={(e) => { setCron(e.target.value); setValidation(null); }} placeholder="*/15 * * * *" />
              <SecondaryButton type="button" icon={<CalendarCheck2 size={16} />} onClick={validateCron} className="mt-1.5 shrink-0">
                Validar cron
              </SecondaryButton>
            </div>
            {validation && (
              <div className={`mt-2 rounded-lg border px-3 py-2 text-xs ${validation.valid ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-red-200 bg-red-50 text-red-700"}`}>
                {validation.valid ? (
                  <div className="flex items-start gap-1.5">
                    <CheckCircle2 size={14} className="mt-0.5 shrink-0" />
                    <div>
                      <div className="font-medium">Próximas execuções:</div>
                      {validation.next_runs.map((r) => <div key={r} className="font-mono">{fmtDateTime(r)}</div>)}
                    </div>
                  </div>
                ) : (
                  <span className="flex items-center gap-1.5"><XCircle size={14} /> {validation.error}</span>
                )}
              </div>
            )}
          </div>
        )}

        <div>
          <label className={label}>Início (opcional)</label>
          <input type="datetime-local" className={field} value={startAt} onChange={(e) => setStartAt(e.target.value)} />
        </div>
        <div>
          <label className={label}>Fim (opcional)</label>
          <input type="datetime-local" className={field} value={endAt} onChange={(e) => setEndAt(e.target.value)} />
        </div>

        <div className="sm:col-span-2">
          <label className={label}>Parâmetros do job (JSON)</label>
          <textarea className={`${field} h-16 font-mono text-xs`} value={paramsText} onChange={(e) => setParamsText(e.target.value)} placeholder='{"date": "2026-07-07"}' />
        </div>

        <label className="flex items-center gap-2 text-sm text-gray-700">
          <input type="checkbox" className="h-4 w-4 rounded border-gray-300 text-brand-500 focus:ring-brand-500/30" checked={active} onChange={(e) => setActive(e.target.checked)} />
          Agendamento ativo
        </label>
      </div>

      {error && <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

      <div className="mt-6 flex items-center justify-end gap-2">
        <SecondaryButton type="button" onClick={onCancel}>Cancelar</SecondaryButton>
        <PrimaryButton type="submit" loading={saving}>Salvar</PrimaryButton>
      </div>
    </form>
  );
}
