import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { SecondaryButton } from "@/components/ui";
import { Modal } from "@/components/ui/Modal";
import { AtivoBadge, IngestionControlStatusBadge } from "@/features/ingestion-control/IngestionControlStatusBadge";
import type { IngestionControl } from "@/features/ingestion-control/types";
import { fmtDate } from "@/features/ingestion-control/types";

interface ControlDestination {
  id: number; destination_role: string; write_order: number;
  destination: {
    name: string; destination_type: string; target_layer: string | null;
    target_schema: string | null; target_table: string | null; target_path: string | null;
    write_mode: string | null; file_format: string | null; partition_columns: string[] | null;
  } | null;
}
const ROLE_LABEL: Record<string, string> = {
  primary: "Destino principal", datalake_copy: "Cópia Data Lake", audit_copy: "Cópia de auditoria",
};

function DestinationsSection({ controlId }: { controlId: number }) {
  const { data } = useQuery({
    queryKey: ["control-destinations", controlId],
    queryFn: () => api.get<ControlDestination[]>(`/api/v1/ingestion-control/${controlId}/destinations`),
  });
  const links = data ?? [];
  if (links.length === 0) return null;
  return (
    <>
      <SectionTitle>Destinos da carga (multi-destino)</SectionTitle>
      <div className="col-span-2 space-y-2">
        {links.map((l) => {
          const d = l.destination;
          const bits = d?.destination_type === "s3"
            ? [d?.target_layer, "parquet", (d?.partition_columns || []).join("/")].filter(Boolean)
            : [d?.target_schema && d?.target_table ? `${d.target_schema}.${d.target_table}` : null, d?.write_mode].filter(Boolean);
          return (
            <div key={l.id} className="flex items-start gap-3 rounded-lg border border-gray-100 bg-gray-50/60 px-3 py-2">
              <span className="mt-0.5 rounded bg-brand-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-brand-700">
                {l.write_order}. {ROLE_LABEL[l.destination_role] ?? l.destination_role}
              </span>
              <div className="min-w-0">
                <div className="text-sm font-medium text-gray-800">{d?.name ?? "—"} <span className="text-gray-400">· {d?.destination_type}</span></div>
                <div className="truncate font-mono text-xs text-gray-500">{d?.target_path || bits.join(" · ")}</div>
              </div>
            </div>
          );
        })}
      </div>
    </>
  );
}

function Field({ label, children, mono }: { label: string; children: ReactNode; mono?: boolean }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-gray-400">{label}</dt>
      <dd className={`mt-0.5 text-sm text-gray-800 ${mono ? "font-mono text-xs" : ""}`}>{children}</dd>
    </div>
  );
}

function SectionTitle({ children }: { children: ReactNode }) {
  return <h3 className="col-span-2 mt-2 border-t border-gray-100 pt-3 text-xs font-semibold uppercase tracking-wide text-brand-600 first:mt-0 first:border-0 first:pt-0">{children}</h3>;
}

export function IngestionControlDetail({ item, onClose }: { item: IngestionControl | null; onClose: () => void }) {
  return (
    <Modal
      open={!!item}
      onClose={onClose}
      title={item?.nome_tabela ?? "Controle de ingestão"}
      description={item?.observacao ?? undefined}
      width="max-w-2xl"
      footer={<SecondaryButton onClick={onClose}>Fechar</SecondaryButton>}
    >
      {item && (
        <dl className="grid grid-cols-2 gap-x-4 gap-y-3">
          <SectionTitle>Resumo</SectionTitle>
          <Field label="Grupo">{item.grupo ?? "—"}</Field>
          <Field label="Tipo da tabela">{item.tipo_tabela ?? "—"}</Field>
          <Field label="Status"><IngestionControlStatusBadge status={item.status} /></Field>
          <Field label="Ativo"><AtivoBadge ativo={item.ativo} /></Field>

          <SectionTitle>Origem e destino</SectionTitle>
          <Field label="Origem">{item.origem ?? "—"}</Field>
          <Field label="Destino">{item.destino ?? "—"}</Field>
          <Field label="Origem ID" mono>{item.origem_id ?? "—"}</Field>
          <Field label="Tipo de ingestão">{item.tipo_ingestao ?? "—"}</Field>

          <DestinationsSection controlId={item.id} />

          <SectionTitle>Parâmetros de ingestão</SectionTitle>
          <Field label="Coluna de data" mono>{item.coluna_data ?? "—"}</Field>
          <Field label="Coluna última alteração" mono>{item.coluna_ultima_alteracao ?? "—"}</Field>
          <Field label="Colunas chave" mono>{item.colunas_chave ?? "—"}</Field>
          <Field label="Watermark atual">{fmtDate(item.watermark_atual)}</Field>

          <SectionTitle>Dados sensíveis</SectionTitle>
          <div className="col-span-2"><Field label="Colunas sensíveis" mono>{item.dados_sensiveis ?? "—"}</Field></div>

          <SectionTitle>Auditoria</SectionTitle>
          <Field label="Criado em">{fmtDate(item.criado_em)}</Field>
          <Field label="Atualizado em">{fmtDate(item.atualizado_em)}</Field>
          <Field label="Última execução">{fmtDate(item.ultima_execucao)}</Field>
        </dl>
      )}
    </Modal>
  );
}
