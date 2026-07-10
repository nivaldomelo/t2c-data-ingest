import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle, Bell, Check, Plus, RefreshCw, Send, Trash2, Webhook,
} from "lucide-react";

import { api, ApiError, type Page } from "@/lib/api";
import { Card, EmptyState, Modal, PageHeader, PrimaryButton, SecondaryButton } from "@/components/ui";
import { cn } from "@/lib/cn";
import { useAuth } from "@/lib/auth";

interface Channel {
  id: number; name: string; channel_type: string; active: boolean;
  events: string[] | null; min_severity: string; target_masked: string | null; created_by: string | null;
}
interface Notification {
  id: number; channel_id: number | null; channel_name: string | null; event_type: string; severity: string;
  title: string; status: string; http_status: number | null; error: string | null; created_at: string; sent_at: string | null;
}

const EVENTS = ["JOB_FAILED", "PIPELINE_FAILED", "JOB_ZERO_RECORDS", "SCHEDULE_OVERDUE", "CONNECTION_FAILED", "CLUSTER_UNAVAILABLE", "WORKER_DOWN", "SCHEMA_CHANGED", "RUNTIME_INVALID"];
const SEV = ["info", "warning", "critical"];
const SEV_TONE: Record<string, string> = { info: "text-sky-600", warning: "text-amber-600", critical: "text-red-600" };
const STATUS_TONE: Record<string, string> = {
  sent: "border-emerald-200 bg-emerald-50 text-emerald-700",
  failed: "border-red-200 bg-red-50 text-red-700",
  pending: "border-sky-200 bg-sky-50 text-sky-700",
};
const inputCls = "w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20";
const labelCls = "mb-1 block text-xs font-medium text-gray-600";
function fmt(t: string | null): string { return t ? new Date(t).toLocaleString("pt-BR") : "—"; }

export default function AlertsPage() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const canManage = can("ingest:alerts:manage");
  const [modal, setModal] = useState<{ mode: "create" | "edit"; ch?: Channel } | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const { data: channels } = useQuery({ queryKey: ["alert-channels"], queryFn: () => api.get<Channel[]>("/api/v1/alerts/channels") });
  const { data: notifs } = useQuery({
    queryKey: ["alert-notifications"], queryFn: () => api.get<Page<Notification>>("/api/v1/alerts/notifications?page=1&page_size=30"),
    refetchInterval: (q) => ((q.state.data as Page<Notification> | undefined)?.items.some((n) => n.status === "pending") ? 3000 : false),
  });

  const flash = (m: string) => { setToast(m); setTimeout(() => setToast(null), 3500); };
  const test = useMutation({
    mutationFn: (id: number) => api.post<{ status: string; error: string | null }>(`/api/v1/alerts/channels/${id}/test`, {}),
    onSuccess: (r) => { flash(r.status === "sent" ? "Teste enviado com sucesso." : `Falha no teste: ${r.error ?? ""}`); qc.invalidateQueries({ queryKey: ["alert-notifications"] }); },
  });
  const del = useMutation({
    mutationFn: (id: number) => api.del(`/api/v1/alerts/channels/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alert-channels"] }),
  });
  const resend = useMutation({
    mutationFn: (id: number) => api.post(`/api/v1/alerts/notifications/${id}/resend`, {}),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["alert-notifications"] }); flash("Reenvio disparado."); },
  });

  return (
    <div>
      <PageHeader
        icon={<Bell size={22} />}
        title="Alertas e notificações"
        description="Envie falhas, atrasos e eventos importantes para Teams, Slack ou webhooks."
        actions={canManage && <PrimaryButton icon={<Plus size={16} />} onClick={() => setModal({ mode: "create" })}>Novo canal</PrimaryButton>}
      />

      {toast && <div className="mb-4 rounded-lg border border-brand-200 bg-brand-50 px-3.5 py-2 text-sm text-brand-800">{toast}</div>}

      {/* Channels */}
      <h2 className="mb-3 text-sm font-semibold text-gray-900">Canais</h2>
      {(channels ?? []).length === 0 ? (
        <Card className="mb-8 py-2">
          <EmptyState icon={<Webhook size={24} />} title="Nenhum canal configurado"
            description="Cadastre um webhook (Teams, Slack ou genérico) para receber alertas de falhas e eventos."
            action={canManage ? <PrimaryButton icon={<Plus size={16} />} onClick={() => setModal({ mode: "create" })}>Novo canal</PrimaryButton> : undefined} />
        </Card>
      ) : (
        <div className="mb-8 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
          {(channels ?? []).map((c) => (
            <Card key={c.id} className="p-4">
              <div className="flex items-start justify-between">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-gray-900">{c.name}</span>
                    <span className="rounded bg-gray-100 px-1.5 py-0.5 text-[11px] font-medium uppercase text-gray-600">{c.channel_type}</span>
                  </div>
                  <p className="mt-0.5 truncate font-mono text-xs text-gray-400">{c.target_masked}</p>
                </div>
                <span className={cn("inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium",
                  c.active ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-gray-200 bg-gray-100 text-gray-500")}>
                  <span className={cn("h-1.5 w-1.5 rounded-full", c.active ? "bg-emerald-500" : "bg-gray-400")} />{c.active ? "Ativo" : "Inativo"}
                </span>
              </div>
              <p className="mt-2 text-xs text-gray-500">Severidade mínima: <span className={cn("font-medium", SEV_TONE[c.min_severity])}>{c.min_severity}</span></p>
              <p className="mt-0.5 text-xs text-gray-400">{(c.events && c.events.length) ? `${c.events.length} evento(s)` : "Todos os eventos"}</p>
              {canManage && (
                <div className="mt-3 flex flex-wrap gap-2">
                  <button onClick={() => test.mutate(c.id)} disabled={test.isPending} className="inline-flex items-center gap-1.5 rounded-md border border-gray-200 bg-white px-2.5 py-1 text-xs font-medium text-gray-600 hover:bg-gray-50 disabled:opacity-50"><Send size={13} /> Testar</button>
                  <button onClick={() => setModal({ mode: "edit", ch: c })} className="inline-flex items-center gap-1.5 rounded-md border border-gray-200 bg-white px-2.5 py-1 text-xs font-medium text-gray-600 hover:bg-gray-50">Editar</button>
                  <button onClick={() => { if (confirm(`Excluir o canal ${c.name}?`)) del.mutate(c.id); }} className="inline-flex items-center gap-1.5 rounded-md border border-red-200 bg-white px-2.5 py-1 text-xs font-medium text-red-600 hover:bg-red-50"><Trash2 size={13} /></button>
                </div>
              )}
            </Card>
          ))}
        </div>
      )}

      {/* History */}
      <h2 className="mb-3 text-sm font-semibold text-gray-900">Histórico de notificações</h2>
      <Card className="overflow-hidden p-0">
        {(notifs?.items ?? []).length === 0 ? (
          <EmptyState icon={<Bell size={22} />} title="Nenhuma notificação" description="Alertas enviados aparecerão aqui com status de entrega." />
        ) : (
          <table className="min-w-full text-sm">
            <thead><tr className="border-b border-gray-100 bg-gray-50/70 text-xs uppercase text-gray-500">
              <th className="px-5 py-2.5 text-left">Evento</th><th className="px-5 py-2.5 text-left">Título</th>
              <th className="px-5 py-2.5 text-left">Canal</th><th className="px-5 py-2.5 text-left">Status</th>
              <th className="px-5 py-2.5 text-left">Quando</th><th className="px-5 py-2.5 text-right">Ações</th>
            </tr></thead>
            <tbody>
              {(notifs?.items ?? []).map((n) => (
                <tr key={n.id} className="border-b border-gray-50 last:border-0">
                  <td className="px-5 py-2.5"><span className="font-mono text-xs text-gray-700">{n.event_type}</span><div className={cn("text-[11px] font-medium", SEV_TONE[n.severity])}>{n.severity}</div></td>
                  <td className="px-5 py-2.5 text-gray-800">{n.title}{n.error && <div className="text-[11px] text-red-500">{n.error}</div>}</td>
                  <td className="px-5 py-2.5 text-xs text-gray-500">{n.channel_name ?? "—"}</td>
                  <td className="px-5 py-2.5"><span className={cn("inline-flex rounded-full border px-2 py-0.5 text-xs font-medium", STATUS_TONE[n.status] ?? STATUS_TONE.pending)}>{n.status}{n.http_status ? ` · ${n.http_status}` : ""}</span></td>
                  <td className="px-5 py-2.5 text-xs text-gray-500">{fmt(n.sent_at ?? n.created_at)}</td>
                  <td className="px-5 py-2.5 text-right">
                    {canManage && n.status === "failed" && (
                      <button onClick={() => resend.mutate(n.id)} className="inline-flex items-center gap-1.5 rounded-md border border-gray-200 bg-white px-2.5 py-1 text-xs font-medium text-gray-600 hover:bg-gray-50"><RefreshCw size={13} /> Reenviar</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {modal && <ChannelModal mode={modal.mode} channel={modal.ch} onClose={() => { setModal(null); qc.invalidateQueries({ queryKey: ["alert-channels"] }); }} />}
    </div>
  );
}

function ChannelModal({ mode, channel, onClose }: { mode: "create" | "edit"; channel?: Channel; onClose: () => void }) {
  const [name, setName] = useState(channel?.name ?? "");
  const [type, setType] = useState(channel?.channel_type ?? "webhook");
  const [url, setUrl] = useState("");
  const [minSev, setMinSev] = useState(channel?.min_severity ?? "warning");
  const [events, setEvents] = useState<string[]>(channel?.events ?? []);
  const [active, setActive] = useState(channel?.active ?? true);
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: () => {
      const body: Record<string, unknown> = { name: name.trim(), channel_type: type, min_severity: minSev, events, active };
      if (url.trim()) body.target_url = url.trim();
      return mode === "create"
        ? api.post("/api/v1/alerts/channels", body)
        : api.patch(`/api/v1/alerts/channels/${channel!.id}`, body);
    },
    onSuccess: onClose,
    onError: (e) => setError(e instanceof ApiError ? e.message : "Falha ao salvar."),
  });

  function submit() {
    setError(null);
    if (!name.trim()) return setError("Informe o nome do canal.");
    if (mode === "create" && !url.trim()) return setError(type === "email" ? "Informe o(s) e-mail(s) destinatário(s)." : "Informe a URL do webhook.");
    save.mutate();
  }

  return (
    <Modal open onClose={onClose} title={mode === "create" ? "Novo canal de alerta" : "Editar canal"}
      description="Teams e Slack aceitam webhooks de entrada; use 'webhook' para um endpoint genérico."
      width="max-w-lg"
      footer={<><SecondaryButton onClick={onClose}>Cancelar</SecondaryButton><PrimaryButton loading={save.isPending} onClick={submit}>Salvar</PrimaryButton></>}>
      {error && <div className="mb-4 flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-3.5 py-2 text-sm text-red-700"><AlertTriangle size={16} className="mt-0.5 shrink-0" /> {error}</div>}
      <div className="space-y-4">
        <div><label className={labelCls}>Nome *</label><input className={inputCls} value={name} onChange={(e) => setName(e.target.value)} placeholder="ex.: Time de Dados — Teams" /></div>
        <div className="grid grid-cols-2 gap-4">
          <div><label className={labelCls}>Tipo</label><select className={inputCls} value={type} onChange={(e) => setType(e.target.value)}><option value="webhook">Webhook genérico</option><option value="teams">Microsoft Teams</option><option value="slack">Slack</option><option value="email">E-mail</option></select></div>
          <div><label className={labelCls}>Severidade mínima</label><select className={inputCls} value={minSev} onChange={(e) => setMinSev(e.target.value)}>{SEV.map((s) => <option key={s} value={s}>{s}</option>)}</select></div>
        </div>
        <div>
          <label className={labelCls}>{type === "email" ? "E-mail(s) destinatário(s)" : "URL do webhook"} {mode === "edit" && <span className="text-gray-400">(deixe vazio para manter)</span>}</label>
          <input className={`${inputCls} font-mono text-xs`} value={url} onChange={(e) => setUrl(e.target.value)} placeholder={type === "email" ? "ops@empresa.com, oncall@empresa.com" : "https://…"} />
        </div>
        <div>
          <label className={labelCls}>Eventos (vazio = todos)</label>
          <div className="flex flex-wrap gap-1.5">
            {EVENTS.map((ev) => {
              const on = events.includes(ev);
              return (
                <button key={ev} onClick={() => setEvents((p) => on ? p.filter((x) => x !== ev) : [...p, ev])}
                  className={cn("rounded-full border px-2 py-0.5 text-[11px] font-medium", on ? "border-brand-500 bg-brand-50 text-brand-700" : "border-gray-200 bg-white text-gray-500 hover:bg-gray-50")}>
                  {on ? <Check size={10} className="mr-0.5 inline" /> : null}{ev}
                </button>
              );
            })}
          </div>
        </div>
        <label className="inline-flex items-center gap-2 text-sm text-gray-700"><input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} className="h-4 w-4 rounded border-gray-300 text-brand-500 focus:ring-brand-500" /> Canal ativo</label>
      </div>
    </Modal>
  );
}
