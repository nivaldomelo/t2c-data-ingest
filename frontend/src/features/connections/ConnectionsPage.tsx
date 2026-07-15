import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plug, Plus, Search } from "lucide-react";

import { api } from "@/lib/api";
import type { Page } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { PageHeader, PrimaryButton, SecondaryButton, HelpBanner } from "@/components/ui";
import { Modal } from "@/components/ui/Modal";
import { ConnectionSummaryCards } from "@/features/connections/ConnectionSummaryCards";
import { ConnectionTable } from "@/features/connections/ConnectionTable";
import { ConnectionForm } from "@/features/connections/ConnectionForm";
import type { ConnectionSubmitPayload } from "@/features/connections/ConnectionForm";
import { DynamicConnectionForm } from "@/features/connections/DynamicConnectionForm";
import { ConnectionTypePicker } from "@/features/connections/ConnectionTypePicker";
import { ConnectionStatusBadge } from "@/features/connections/ConnectionStatusBadge";
import { S3ConnectionDetail } from "@/features/connections/S3ConnectionDetail";
import { useConnectors } from "@/features/connections/useConnectors";
import type {
  Connection,
  ConnectionSummary,
  ConnectionTestResult,
  ConnectorMeta,
} from "@/features/connections/types";
import { CATEGORY_LABEL, typeLabel } from "@/features/connections/types";

// Formulário dedicado (rico) para estes; os demais usam o formulário dinâmico via registry.
const NATIVE_FORM_TYPES = new Set(["postgres", "mysql", "s3"]);

const selectCls =
  "h-10 rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-700 focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-500/20";

export default function ConnectionsPage() {
  const { can } = useAuth();
  const qc = useQueryClient();

  const [type, setType] = useState("");
  const [category, setCategory] = useState("");
  const [status, setStatus] = useState("");
  const [active, setActive] = useState("");
  const [q, setQ] = useState("");

  const connectors = useConnectors();
  const [pickedType, setPickedType] = useState<ConnectorMeta | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Connection | null>(null);
  const [viewing, setViewing] = useState<Connection | null>(null);
  const [deleting, setDeleting] = useState<Connection | null>(null);
  const [formTestResult, setFormTestResult] = useState<ConnectionTestResult | null>(null);
  const [testingId, setTestingId] = useState<number | null>(null);

  const perms = {
    write: can("ingest:connections:write"),
    test: can("ingest:connections:test"),
    del: can("ingest:connections:delete"),
  };

  const query = useMemo(() => {
    const p = new URLSearchParams({ page: "1", page_size: "100" });
    if (type) p.set("connection_type", type);
    if (status) p.set("last_test_status", status);
    if (active) p.set("active", active);
    if (q.trim()) p.set("q", q.trim());
    return p.toString();
  }, [type, status, active, q]);

  const summary = useQuery({
    queryKey: ["connections-summary"],
    queryFn: () => api.get<ConnectionSummary>("/api/v1/connections/summary"),
  });
  const list = useQuery({
    queryKey: ["connections", query],
    queryFn: () => api.get<Page<Connection>>(`/api/v1/connections?${query}`),
  });

  function refresh() {
    qc.invalidateQueries({ queryKey: ["connections"] });
    qc.invalidateQueries({ queryKey: ["connections-summary"] });
  }

  const save = useMutation({
    mutationFn: ({ payload, id }: { payload: ConnectionSubmitPayload; id?: number }) =>
      id
        ? api.put<Connection>(`/api/v1/connections/${id}`, payload)
        : api.post<Connection>("/api/v1/connections", payload),
  });

  const test = useMutation({
    mutationFn: (id: number) => api.post<ConnectionTestResult>(`/api/v1/connections/${id}/test`, {}),
  });

  const del = useMutation({
    mutationFn: (id: number) => api.del(`/api/v1/connections/${id}`),
  });

  function openCreate() {
    setEditing(null);
    setPickedType(null);
    setFormTestResult(null);
    setFormOpen(true);
  }
  function openEdit(c: Connection) {
    setEditing(c);
    setPickedType(connectors.data?.find((m) => m.type === c.connection_type) ?? null);
    setFormTestResult(null);
    setFormOpen(true);
  }

  async function handleSubmit(payload: ConnectionSubmitPayload, testAfter: boolean) {
    try {
      const saved = await save.mutateAsync({ payload, id: editing?.id });
      refresh();
      if (testAfter) {
        const result = await test.mutateAsync(saved.id);
        setFormTestResult(result);
        setEditing(saved);
        refresh();
      } else {
        setFormOpen(false);
      }
    } catch (err) {
      setFormTestResult({
        status: "failed",
        message: err instanceof Error ? err.message : "Erro ao salvar",
        tested_at: null,
      });
    }
  }

  async function handleRowTest(c: Connection) {
    setTestingId(c.id);
    try {
      await test.mutateAsync(c.id);
    } finally {
      setTestingId(null);
      refresh();
    }
  }

  async function handleDelete() {
    if (!deleting) return;
    try {
      await del.mutateAsync(deleting.id);
      refresh();
    } finally {
      setDeleting(null);
    }
  }

  const rows = useMemo(() => {
    const items = list.data?.items ?? [];
    return category ? items.filter((r) => (r.connection_category ?? "") === category) : items;
  }, [list.data, category]);

  return (
    <div>
      <PageHeader
        icon={<Plug size={22} />}
        title="Origens"
        description="Cadastre e teste as origens de dados (bancos, Data Lake, storages e APIs) usadas pelas cargas, jobs e pipelines."
        actions={
          perms.write ? (
            <PrimaryButton icon={<Plus size={16} />} onClick={openCreate}>
              Nova origem
            </PrimaryButton>
          ) : null
        }
      />

      <ConnectionSummaryCards summary={summary.data} loading={summary.isLoading} />

      {/* Filtros */}
      <div className="mt-6 flex flex-wrap items-center gap-2">
        <div className="relative min-w-[220px] flex-1">
          <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Buscar por nome, host ou banco…"
            className="h-10 w-full rounded-lg border border-gray-200 bg-white pl-9 pr-3 text-sm text-gray-700 placeholder:text-gray-400 focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
          />
        </div>
        <select className={selectCls} value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="">Todas as categorias</option>
          <option value="database">Bancos de dados</option>
          <option value="storage">Data Lake / Storage</option>
          <option value="api">APIs / SaaS</option>
        </select>
        <select className={selectCls} value={type} onChange={(e) => setType(e.target.value)}>
          <option value="">Todos os tipos</option>
          {(connectors.data ?? [])
            .filter((m) => !category || m.category === category)
            .map((m) => <option key={m.type} value={m.type}>{m.label}</option>)}
        </select>
        <select className={selectCls} value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">Qualquer teste</option>
          <option value="success">Conectado</option>
          <option value="failed">Falhou</option>
          <option value="not_tested">Não testado</option>
        </select>
        <select className={selectCls} value={active} onChange={(e) => setActive(e.target.value)}>
          <option value="">Ativos e inativos</option>
          <option value="true">Somente ativos</option>
          <option value="false">Somente inativos</option>
        </select>
      </div>

      <div className="mt-4">
        <ConnectionTable
          rows={rows}
          loading={list.isLoading}
          perms={perms}
          testingId={testingId}
          onView={setViewing}
          onEdit={openEdit}
          onTest={handleRowTest}
          onDelete={setDeleting}
        />
      </div>

      {/* Modal criar/editar */}
      <Modal
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title={editing ? "Editar origem" : pickedType ? `Nova origem · ${pickedType.label}` : "Nova origem"}
        description={
          editing || pickedType
            ? "Configure e teste a origem. Segredos não são exibidos e, ao editar, campos em branco mantêm o valor atual."
            : "Escolha o tipo de origem."
        }
        width="max-w-2xl"
      >
        {!editing && !pickedType ? (
          <div className="space-y-4">
            <HelpBanner title="O que é uma Origem?">
              Uma <b>origem</b> é uma conexão a uma fonte/destino de dados (banco, Data Lake S3, storage ou API).
              As <b>credenciais são criptografadas</b> e usadas apenas no servidor/worker — nunca aparecem na tela
              nem nos logs. Depois de cadastrar, use o botão <b>Testar</b> para validar. Origens são referenciadas
              por Jobs, Destinos e pelo Controle de Ingestão.
            </HelpBanner>
            <ConnectionTypePicker onPick={setPickedType} />
          </div>
        ) : (() => {
          const effectiveType = editing?.connection_type ?? pickedType?.type ?? "postgres";
          if (NATIVE_FORM_TYPES.has(effectiveType)) {
            return (
              <ConnectionForm
                initial={editing}
                forcedType={editing ? undefined : effectiveType}
                saving={save.isPending || test.isPending}
                testResult={formTestResult}
                onSubmit={handleSubmit}
                onCancel={() => setFormOpen(false)}
              />
            );
          }
          if (!pickedType) return <p className="text-sm text-gray-400">Carregando…</p>;
          return (
            <DynamicConnectionForm
              meta={pickedType}
              initial={editing}
              saving={save.isPending || test.isPending}
              testResult={formTestResult}
              onSubmit={handleSubmit}
              onCancel={() => setFormOpen(false)}
            />
          );
        })()}
      </Modal>

      {/* Modal detalhes */}
      <Modal
        open={!!viewing}
        onClose={() => setViewing(null)}
        title={viewing?.name ?? "Conexão"}
        description={viewing?.description ?? undefined}
        width={viewing?.connection_type === "s3" ? "max-w-3xl" : undefined}
        footer={
          <SecondaryButton onClick={() => setViewing(null)}>Fechar</SecondaryButton>
        }
      >
        {viewing && viewing.connection_type === "s3" && <S3ConnectionDetail conn={viewing} />}
        {viewing && viewing.connection_type !== "s3" && (
          <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
            <Detail label="Categoria" value={CATEGORY_LABEL[viewing.connection_category ?? "database"]} />
            <Detail label="Tipo" value={typeLabel(viewing.connection_type, connectors.data)} />
            <Detail label="Último teste" value={<ConnectionStatusBadge status={viewing.last_test_status} />} />
            <Detail label="Ativo" value={viewing.active ? "Sim" : "Não"} />
            {viewing.connection_category === "api" ? (
              <div className="col-span-2">
                <Detail label="Base URL" value={String((viewing.extra_params as Record<string, unknown> | null)?.base_url ?? "—")} mono />
              </div>
            ) : (
              <>
                <Detail label="Host" value={viewing.host ?? "—"} mono />
                <Detail label="Porta" value={viewing.port ?? "—"} />
                <Detail label="Banco" value={viewing.database_name ?? "—"} />
                <Detail label="Schema" value={viewing.schema_name ?? "—"} />
                <Detail label="Usuário" value={viewing.username ?? "—"} />
              </>
            )}
            <Detail label="Permissões" value={`${viewing.can_read ? "leitura" : ""}${viewing.can_read && viewing.can_write ? " + " : ""}${viewing.can_write ? "escrita" : ""}` || "—"} />
            <Detail
              label="Segredos"
              value={
                viewing.has_password || viewing.secrets_present.length
                  ? `•••••••• (${[viewing.has_password ? "senha" : null, ...viewing.secrets_present].filter(Boolean).join(", ")})`
                  : "nenhum cadastrado"
              }
            />
            {viewing.last_test_message && (
              <div className="col-span-2">
                <Detail label="Mensagem do teste" value={viewing.last_test_message} />
              </div>
            )}
          </dl>
        )}
      </Modal>

      {/* Confirmar remoção */}
      <Modal
        open={!!deleting}
        onClose={() => setDeleting(null)}
        title="Remover conexão"
        footer={
          <>
            <SecondaryButton onClick={() => setDeleting(null)}>Cancelar</SecondaryButton>
            <PrimaryButton
              className="bg-red-600 hover:bg-red-700"
              loading={del.isPending}
              onClick={handleDelete}
            >
              Remover
            </PrimaryButton>
          </>
        }
      >
        <p className="text-sm text-gray-600">
          Tem certeza que deseja remover a conexão <span className="font-semibold text-gray-900">{deleting?.name}</span>?
          Esta ação não pode ser desfeita.
        </p>
      </Modal>
    </div>
  );
}

function Detail({ label, value, mono }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-gray-400">{label}</dt>
      <dd className={`mt-0.5 text-gray-800 ${mono ? "font-mono text-xs" : ""}`}>{value}</dd>
    </div>
  );
}
