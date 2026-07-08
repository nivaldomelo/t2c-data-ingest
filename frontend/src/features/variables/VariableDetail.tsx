import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { api } from "@/lib/api";
import { CodeViewer, SecondaryButton } from "@/components/ui";
import { Modal } from "@/components/ui/Modal";
import { Skeleton } from "@/components/ui/LoadingSkeleton";
import { cn } from "@/lib/cn";
import { TypeBadge, VariableSecretBadge, VariableStatusBadge } from "@/features/variables/VariableBadges";
import type { Variable, VariableDetail as VDetail } from "@/features/variables/types";
import { fmtDate } from "@/features/variables/types";

type Tab = "resumo" | "uso" | "auditoria";

function Field({ label, children, mono }: { label: string; children: ReactNode; mono?: boolean }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-gray-400">{label}</dt>
      <dd className={`mt-0.5 text-sm text-gray-800 ${mono ? "font-mono text-xs" : ""}`}>{children}</dd>
    </div>
  );
}

export function VariableDetail({ item, onClose }: { item: Variable | null; onClose: () => void }) {
  const [tab, setTab] = useState<Tab>("resumo");
  const { data } = useQuery({
    queryKey: ["variable-detail", item?.id],
    queryFn: () => api.get<VDetail>(`/api/v1/variables/${item!.id}`),
    enabled: !!item,
  });

  const v = data ?? item;

  const tabs: { key: Tab; label: string }[] = [
    { key: "resumo", label: "Resumo" },
    { key: "uso", label: "Como usar" },
    { key: "auditoria", label: "Auditoria" },
  ];

  return (
    <Modal open={!!item} onClose={onClose} title={item?.name ?? "Variável"} description={item?.description ?? undefined} width="max-w-3xl" footer={<SecondaryButton onClick={onClose}>Fechar</SecondaryButton>}>
      <div className="mb-4 flex gap-1 border-b border-gray-200">
        {tabs.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={cn("-mb-px border-b-2 px-3 py-2 text-sm font-medium transition-colors",
              tab === t.key ? "border-brand-500 text-brand-600" : "border-transparent text-gray-500 hover:text-gray-700")}>
            {t.label}
          </button>
        ))}
      </div>

      {!v ? (
        <Skeleton className="h-40 rounded-xl" />
      ) : tab === "resumo" ? (
        <dl className="grid grid-cols-2 gap-x-4 gap-y-3">
          <Field label="Nome" mono>{v.name}</Field>
          <Field label="Tipo"><TypeBadge type={v.variable_type} /></Field>
          <Field label="Escopo">{v.scope}</Field>
          <Field label="Ambiente">{v.environment ?? "—"}</Field>
          <Field label="Valor" mono>{v.is_secret ? "•••••••• (protegido)" : v.value ?? "—"}</Field>
          <Field label="Secreta"><VariableSecretBadge isSecret={v.is_secret} /></Field>
          <Field label="Ativa"><VariableStatusBadge active={v.active} /></Field>
          <Field label="Criado por">{v.created_by ?? "—"}</Field>
          <Field label="Atualizado por">{v.updated_by ?? "—"}</Field>
          <Field label="Criado em">{fmtDate(v.created_at)}</Field>
          <Field label="Atualizado em">{fmtDate(v.updated_at)}</Field>
        </dl>
      ) : tab === "uso" ? (
        <div className="space-y-4">
          <p className="text-sm text-gray-500">
            A variável é injetada como <span className="font-mono">variável de ambiente</span> no
            runtime do job. Exemplos:
          </p>
          <CodeViewer language="python" path="Python" content={data?.usage?.python ?? "# carregando…"} />
          <CodeViewer language="python" path="Spark (PySpark)" content={data?.usage?.spark ?? "# carregando…"} />
        </div>
      ) : (
        <div className="text-sm text-gray-500">
          <p>As ações sobre esta variável são registradas em <span className="font-mono">audit_events</span>
            {" "}(criação, edição, ativação/inativação, remoção). O valor de variáveis secretas nunca é
            registrado.</p>
          <p className="mt-2 text-xs text-gray-400">Criada em {fmtDate(v.created_at)} · atualizada em {fmtDate(v.updated_at)}.</p>
        </div>
      )}
    </Modal>
  );
}
