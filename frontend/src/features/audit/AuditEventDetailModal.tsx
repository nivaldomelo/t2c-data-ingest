import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Fingerprint, Loader2, RefreshCw } from "lucide-react";

import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import {
  DetailModalShell,
  JsonViewer,
  ModalField,
  ModalSection,
  SecondaryButton,
} from "@/components/ui";

export interface AuditEvent {
  id: number;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  user_email: string | null;
  ip_address: string | null;
  detail: unknown;
  created_at: string;
}

export function actionTone(a: string): string {
  if (/DELETE|FAILED|BLOCKED|REMOVED/i.test(a)) return "text-red-600 bg-red-50 border-red-200";
  if (/CREATED|SUCCEEDED|ACTIVATED|ADDED/i.test(a)) return "text-emerald-600 bg-emerald-50 border-emerald-200";
  if (/UPDATED|RESET|REQUESTED|STARTED|RENAMED/i.test(a)) return "text-amber-600 bg-amber-50 border-amber-200";
  return "text-gray-700 bg-gray-50 border-gray-200";
}

function fmt(t: string): string {
  return new Date(t).toLocaleString("pt-BR");
}

/** Payloads "antes/depois" quando o detalhe traz esses formatos; senão, exibe o detalhe inteiro. */
function splitPayloads(detail: unknown): { before?: unknown; after?: unknown } | null {
  if (!detail || typeof detail !== "object" || Array.isArray(detail)) return null;
  const d = detail as Record<string, unknown>;
  const before = d.before ?? d.antes ?? d.old ?? d.previous;
  const after = d.after ?? d.depois ?? d.new ?? d.current;
  if (before === undefined && after === undefined) return null;
  return { before, after };
}

export function AuditEventDetailModal({
  eventId,
  seed,
  onClose,
}: {
  eventId: number | null;
  seed?: AuditEvent;
  onClose: () => void;
}) {
  const open = eventId != null;
  const query = useQuery({
    queryKey: ["audit-event", eventId],
    queryFn: () => api.get<AuditEvent>(`/api/v1/audit/events/${eventId}`),
    enabled: open,
    placeholderData: seed,
  });

  const data = query.data ?? seed;
  const loading = open && query.isLoading && !data;
  const errored = open && query.isError && !data;
  const payloads = data ? splitPayloads(data.detail) : null;
  const hasDetail = data?.detail != null && (typeof data.detail !== "object" || Object.keys(data.detail as object).length > 0);

  return (
    <DetailModalShell
      open={open}
      onClose={onClose}
      icon={<Fingerprint size={20} />}
      title={data?.action ?? "Evento de auditoria"}
      subtitle={
        data
          ? `${data.entity_type ?? "—"}${data.entity_id ? ` #${data.entity_id}` : ""} · ${fmt(data.created_at)}`
          : "Auditoria"
      }
      status={
        data ? (
          <span className={cn("inline-flex rounded-full border px-2.5 py-0.5 font-mono text-xs font-medium", actionTone(data.action))}>
            {data.action}
          </span>
        ) : undefined
      }
    >
      {loading ? (
        <div className="flex flex-col items-center justify-center gap-3 py-16 text-gray-400">
          <Loader2 size={26} className="animate-spin text-brand-500" />
          <p className="text-sm">Carregando detalhes…</p>
        </div>
      ) : errored ? (
        <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
          <AlertTriangle size={26} className="text-red-500" />
          <p className="text-sm text-gray-600">Não foi possível carregar os detalhes deste registro.</p>
          <SecondaryButton onClick={() => query.refetch()}>
            <RefreshCw size={15} /> Tentar novamente
          </SecondaryButton>
        </div>
      ) : !data ? null : (
        <>
          <ModalSection title="Resumo do evento">
            <dl className="grid grid-cols-2 gap-x-6 gap-y-4 md:grid-cols-3">
              <ModalField label="Tipo do evento">
                <span className="font-mono text-xs">{data.action}</span>
              </ModalField>
              <ModalField label="Data/hora">{fmt(data.created_at)}</ModalField>
              <ModalField label="ID do evento">#{data.id}</ModalField>
            </dl>
          </ModalSection>

          <ModalSection title="Usuário e origem">
            <dl className="grid grid-cols-2 gap-x-6 gap-y-4 md:grid-cols-3">
              <ModalField label="Usuário">{data.user_email ?? "sistema"}</ModalField>
              <ModalField label="IP / origem">{data.ip_address ?? "—"}</ModalField>
            </dl>
          </ModalSection>

          <ModalSection title="Entidade afetada">
            <dl className="grid grid-cols-2 gap-x-6 gap-y-4 md:grid-cols-3">
              <ModalField label="Tipo">{data.entity_type ?? "—"}</ModalField>
              <ModalField label="ID da entidade">{data.entity_id ?? "—"}</ModalField>
              <ModalField label="Ação executada">
                <span className="font-mono text-xs">{data.action}</span>
              </ModalField>
            </dl>
          </ModalSection>

          <ModalSection title="Alterações">
            {!hasDetail ? (
              <p className="text-sm text-gray-400">Nenhum detalhe adicional disponível.</p>
            ) : payloads ? (
              <div className="grid gap-3 md:grid-cols-2">
                <div>
                  <p className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-gray-400">Antes</p>
                  <JsonViewer data={payloads.before ?? null} label="payload anterior" />
                </div>
                <div>
                  <p className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-gray-400">Depois</p>
                  <JsonViewer data={payloads.after ?? null} label="payload novo" />
                </div>
              </div>
            ) : (
              <JsonViewer data={data.detail} label="detalhe" />
            )}
          </ModalSection>
        </>
      )}
    </DetailModalShell>
  );
}
