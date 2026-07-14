import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2, Cloud, Database, Loader2, Plus, Search, Target, XCircle,
} from "lucide-react";

import { api, ApiError } from "@/lib/api";
import type { Page } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { CodeViewer, DataTable, EmptyState, MetricCard, PageHeader, PrimaryButton, SecondaryButton, StatusBadge } from "@/components/ui";
import type { Column } from "@/components/ui";
import { MetricCardSkeleton } from "@/components/ui/LoadingSkeleton";
import { Modal } from "@/components/ui/Modal";
import { cn } from "@/lib/cn";
import { DestinationForm } from "@/features/destinations/DestinationForm";
import type {
  Destination, DestinationSubmit, DestinationSummary, DestinationTestResult, DestinationType,
} from "@/features/destinations/types";
import { TYPE_LABEL } from "@/features/destinations/types";
import { ConnectionStatusBadge } from "@/features/connections/ConnectionStatusBadge";

const selectCls =
  "h-10 rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-700 focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-500/20";

export default function DestinationsPage() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const perms = {
    create: can("ingest:destinations:create"),
    write: can("ingest:destinations:write"),
    del: can("ingest:destinations:delete"),
    test: can("ingest:destinations:test"),
  };

  const [q, setQ] = useState("");
  const [type, setType] = useState("");
  const [active, setActive] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [picked, setPicked] = useState<DestinationType | null>(null);
  const [editing, setEditing] = useState<Destination | null>(null);
  const [saveErr, setSaveErr] = useState<string | null>(null);
  const [viewing, setViewing] = useState<Destination | null>(null);
  const [deleting, setDeleting] = useState<Destination | null>(null);
  const [testingId, setTestingId] = useState<number | null>(null);

  const query = useMemo(() => {
    const p = new URLSearchParams({ page: "1", page_size: "100" });
    if (type) p.set("destination_type", type);
    if (active) p.set("active", active);
    if (q.trim()) p.set("q", q.trim());
    return p.toString();
  }, [type, active, q]);

  const summary = useQuery({ queryKey: ["destinations-summary"], queryFn: () => api.get<DestinationSummary>("/api/v1/destinations/summary") });
  const list = useQuery({ queryKey: ["destinations", query], queryFn: () => api.get<Page<Destination>>(`/api/v1/destinations?${query}`) });

  function refresh() {
    qc.invalidateQueries({ queryKey: ["destinations"] });
    qc.invalidateQueries({ queryKey: ["destinations-summary"] });
  }

  const save = useMutation({
    mutationFn: ({ payload, id }: { payload: DestinationSubmit; id?: number }) =>
      id ? api.put<Destination>(`/api/v1/destinations/${id}`, payload) : api.post<Destination>("/api/v1/destinations", payload),
    onSuccess: () => { refresh(); setFormOpen(false); },
    onError: (e) => setSaveErr(e instanceof ApiError ? e.message : "Erro ao salvar"),
  });
  const test = useMutation({ mutationFn: (id: number) => api.post<DestinationTestResult>(`/api/v1/destinations/${id}/test`, {}) });
  const del = useMutation({ mutationFn: (id: number) => api.del(`/api/v1/destinations/${id}`) });

  function openCreate() { setEditing(null); setPicked(null); setSaveErr(null); setFormOpen(true); }
  function openEdit(d: Destination) { setEditing(d); setPicked(d.destination_type); setSaveErr(null); setFormOpen(true); }

  async function handleRowTest(d: Destination) {
    setTestingId(d.id);
    try { await test.mutateAsync(d.id); } finally { setTestingId(null); refresh(); }
  }
  async function handleDelete() {
    if (!deleting) return;
    try { await del.mutateAsync(deleting.id); refresh(); } finally { setDeleting(null); }
  }

  const rows = list.data?.items ?? [];

  const columns: Column<Destination>[] = [
    { key: "name", header: "Nome", render: (d) => (<div><div className="font-medium text-gray-900">{d.name}</div>{d.description && <div className="text-xs text-gray-400">{d.description}</div>}</div>) },
    { key: "type", header: "Tipo", render: (d) => <span className="inline-flex rounded-md bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600">{TYPE_LABEL[d.destination_type]}</span> },
    { key: "conn", header: "Conexão", render: (d) => <span className="text-gray-600">{d.connection_name ?? "—"}</span> },
    { key: "target", header: "Alvo", render: (d) => <span className="font-mono text-xs text-gray-600">{d.target_display ?? "—"}</span> },
    { key: "write", header: "Write mode", render: (d) => <span className="text-gray-600">{d.write_mode}</span> },
    { key: "fmt", header: "Formato", render: (d) => <span className="text-gray-500">{d.destination_type === "s3" ? d.file_format ?? "—" : "—"}</span> },
    { key: "test", header: "Último teste", render: (d) => <ConnectionStatusBadge status={d.last_test_status} /> },
    { key: "active", header: "Ativo", render: (d) => <StatusBadge status={d.active ? "active" : "inactive"} /> },
    {
      key: "actions", header: "", align: "right", render: (d) => (
        <div className="flex items-center justify-end gap-0.5">
          <IconBtn title="Ver detalhes" onClick={() => setViewing(d)}><Search size={16} /></IconBtn>
          {perms.test && <IconBtn title="Testar" onClick={() => handleRowTest(d)}>{testingId === d.id ? <Loader2 size={16} className="animate-spin text-brand-500" /> : <CheckCircle2 size={16} />}</IconBtn>}
          {perms.write && <IconBtn title="Editar" onClick={() => openEdit(d)}><Database size={16} /></IconBtn>}
          {perms.del && <IconBtn title="Remover" danger onClick={() => setDeleting(d)}><XCircle size={16} /></IconBtn>}
        </div>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        icon={<Target size={22} />}
        title="Destinos"
        description="Configure destinos reutilizáveis para cargas em PostgreSQL, Data Lake S3 e outros alvos de ingestão."
        actions={perms.create ? <PrimaryButton icon={<Plus size={16} />} onClick={openCreate}>Novo destino</PrimaryButton> : null}
      />

      {summary.isLoading ? (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">{Array.from({ length: 5 }).map((_, i) => <MetricCardSkeleton key={i} />)}</div>
      ) : (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
          <MetricCard label="Total" value={summary.data?.total ?? 0} icon={<Target size={20} />} accent />
          <MetricCard label="PostgreSQL" value={summary.data?.postgres ?? 0} icon={<Database size={20} />} />
          <MetricCard label="S3 / Data Lake" value={summary.data?.s3 ?? 0} icon={<Cloud size={20} />} />
          <MetricCard label="Ativos" value={summary.data?.active ?? 0} icon={<CheckCircle2 size={20} />} tone="success" />
          <MetricCard label="Com falha" value={summary.data?.test_failed ?? 0} icon={<XCircle size={20} />} tone="danger" />
        </div>
      )}

      <div className="mt-6 flex flex-wrap items-center gap-2">
        <div className="relative min-w-[220px] flex-1">
          <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar destino…" className="h-10 w-full rounded-lg border border-gray-200 bg-white pl-9 pr-3 text-sm text-gray-700 placeholder:text-gray-400 focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-500/20" />
        </div>
        <select className={selectCls} value={type} onChange={(e) => setType(e.target.value)}>
          <option value="">Todos os tipos</option>
          <option value="postgres">PostgreSQL</option>
          <option value="s3">AWS S3 / Data Lake</option>
        </select>
        <select className={selectCls} value={active} onChange={(e) => setActive(e.target.value)}>
          <option value="">Ativos e inativos</option>
          <option value="true">Somente ativos</option>
          <option value="false">Somente inativos</option>
        </select>
      </div>

      <div className="mt-4">
        <DataTable
          columns={columns} rows={rows} rowKey={(d) => d.id} loading={list.isLoading} onRowClick={setViewing}
          empty={<EmptyState icon={<Target size={24} />} title="Nenhum destino cadastrado" description="Cadastre um destino PostgreSQL ou S3 / Data Lake reutilizável para suas cargas." />}
        />
      </div>

      {/* Criar / editar */}
      <Modal
        open={formOpen} onClose={() => setFormOpen(false)}
        title={editing ? "Editar destino" : picked ? `Novo destino · ${TYPE_LABEL[picked]}` : "Novo destino"}
        description={editing || picked ? "Configure o destino declarativo. As credenciais ficam na conexão." : "Escolha o tipo de destino."}
        width="max-w-2xl"
      >
        {!editing && !picked ? (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {(["postgres", "s3"] as DestinationType[]).map((t) => (
              <button key={t} onClick={() => setPicked(t)} className="flex items-center gap-3 rounded-xl border border-gray-200 bg-white p-4 text-left transition-colors hover:border-brand-300 hover:bg-brand-50/40">
                {t === "s3" ? <Cloud size={20} className="text-sky-500" /> : <Database size={20} className="text-brand-500" />}
                <span><span className="block text-sm font-medium text-gray-900">{TYPE_LABEL[t]}</span><span className="block text-xs text-gray-400">{t === "s3" ? "Data Lake / arquivos" : "Banco relacional"}</span></span>
              </button>
            ))}
          </div>
        ) : (
          <DestinationForm
            type={editing?.destination_type ?? picked!}
            initial={editing}
            saving={save.isPending}
            error={saveErr}
            onSubmit={(payload) => { setSaveErr(null); save.mutate({ payload, id: editing?.id }); }}
            onCancel={() => setFormOpen(false)}
          />
        )}
      </Modal>

      {/* Detalhe */}
      <Modal open={!!viewing} onClose={() => setViewing(null)} title={viewing?.name ?? "Destino"} description={viewing?.description ?? undefined} width="max-w-2xl"
        footer={<SecondaryButton onClick={() => setViewing(null)}>Fechar</SecondaryButton>}>
        {viewing && <DestinationDetail dest={viewing} canTest={perms.test} />}
      </Modal>

      {/* Remover */}
      <Modal open={!!deleting} onClose={() => setDeleting(null)} title="Remover destino"
        footer={<><SecondaryButton onClick={() => setDeleting(null)}>Cancelar</SecondaryButton><PrimaryButton className="bg-red-600 hover:bg-red-700" loading={del.isPending} onClick={handleDelete}>Remover</PrimaryButton></>}>
        <p className="text-sm text-gray-600">Remover o destino <span className="font-semibold text-gray-900">{deleting?.name}</span>? Jobs/controles que o referenciam deixarão de resolvê-lo.</p>
      </Modal>
    </div>
  );
}

function IconBtn({ title, onClick, children, danger }: { title: string; onClick: () => void; children: React.ReactNode; danger?: boolean }) {
  return (
    <button title={title} onClick={(e) => { e.stopPropagation(); onClick(); }}
      className={cn("inline-flex h-8 w-8 items-center justify-center rounded-lg text-gray-400 transition-colors", danger ? "hover:bg-red-50 hover:text-red-600" : "hover:bg-gray-100 hover:text-gray-700")}>
      {children}
    </button>
  );
}

function DestinationDetail({ dest, canTest }: { dest: Destination; canTest: boolean }) {
  const [tab, setTab] = useState<"resumo" | "config" | "como-usar" | "teste">("resumo");
  const test = useMutation({ mutationFn: () => api.post<DestinationTestResult>(`/api/v1/destinations/${dest.id}/test`, {}) });
  const parts = (dest.partition_columns ?? []).join(", ") || "—";
  const TABS = [
    { id: "resumo" as const, label: "Resumo" },
    { id: "config" as const, label: "Configuração" },
    { id: "como-usar" as const, label: "Como usar" },
    ...(canTest ? [{ id: "teste" as const, label: "Teste" }] : []),
  ];
  return (
    <div>
      <div className="flex gap-1 border-b border-gray-100">
        {TABS.map((t) => (
          <button key={t.id} onClick={() => setTab(t.id)} className={cn("-mb-px border-b-2 px-3 py-2 text-sm font-medium", tab === t.id ? "border-brand-500 text-brand-600" : "border-transparent text-gray-500 hover:text-gray-700")}>{t.label}</button>
        ))}
      </div>
      <div className="pt-4">
        {tab === "como-usar" && <ComoUsarTab dest={dest} />}
        {tab === "resumo" && (
          <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
            <D label="Tipo" v={TYPE_LABEL[dest.destination_type]} />
            <D label="Conexão" v={dest.connection_name ?? "—"} />
            <D label="Alvo" v={<span className="font-mono text-xs">{dest.target_display}</span>} />
            <D label="Write mode" v={dest.write_mode} />
            {dest.destination_type === "s3" ? (
              <>
                <D label="Formato" v={dest.file_format ?? "—"} />
                <D label="Camada" v={dest.target_layer ?? "—"} />
                <D label="Compressão" v={dest.compression ?? "—"} />
                <D label="Partições" v={parts} />
              </>
            ) : (
              <>
                <D label="Chaves" v={(dest.primary_key_columns ?? []).join(", ") || "—"} />
                <D label="Staging" v={dest.staging_table ? `${dest.staging_schema ?? dest.target_schema}.${dest.staging_table}` : "—"} />
              </>
            )}
            <D label="Último teste" v={<ConnectionStatusBadge status={dest.last_test_status} />} />
            <D label="Ativo" v={dest.active ? "Sim" : "Não"} />
          </dl>
        )}
        {tab === "config" && (
          <pre className="max-h-80 overflow-auto rounded-xl border border-gray-100 bg-gray-50 p-3 font-mono text-xs text-gray-700">{JSON.stringify(dest, null, 2)}</pre>
        )}
        {tab === "teste" && canTest && (
          <div className="space-y-3">
            <PrimaryButton loading={test.isPending} onClick={() => test.mutate()}>Testar destino</PrimaryButton>
            {test.data && (
              <div className={cn("rounded-xl border p-3", test.data.status === "success" ? "border-emerald-200 bg-emerald-50" : "border-red-200 bg-red-50")}>
                <p className={cn("text-sm font-medium", test.data.status === "success" ? "text-emerald-800" : "text-red-800")}>{test.data.message}</p>
                <div className="mt-2 space-y-1">
                  {test.data.checks.map((c) => (
                    <div key={c.name} className="flex items-center gap-2 text-xs text-gray-600">
                      {c.ok ? <CheckCircle2 size={13} className="text-emerald-600" /> : <XCircle size={13} className="text-red-500" />}
                      <span className="font-medium">{c.name}</span>{c.detail && <span className="text-gray-400">· {c.detail}</span>}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function D({ label, v }: { label: string; v: React.ReactNode }) {
  return <div><dt className="text-xs font-medium uppercase tracking-wide text-gray-400">{label}</dt><dd className="mt-0.5 text-gray-800">{v}</dd></div>;
}

function sub(val: string | null | undefined, table: string): string {
  return (val ?? "").replace(/\{table\}|\{nome_tabela\}/g, table);
}

function ComoUsarTab({ dest }: { dest: Destination }) {
  const isS3 = dest.destination_type === "s3";
  const example = "clientes"; // tabela de exemplo p/ ilustrar um destino template
  const tbl = dest.is_template ? example : (isS3 ? "" : dest.target_table ?? "");

  // Prévia do que o runner injeta (TARGET_*), mesma lógica do resolver.
  const env: string[] = [`TARGET_TYPE=${dest.destination_type}`, `TARGET_CONNECTION_NAME=${dest.connection_name ?? ""}`];
  if (isS3) {
    const base = (dest.target_prefix ?? "").replace(/^\/+|\/+$/g, "");
    const prefix = base.includes("{table}") ? sub(base, tbl) : (dest.is_template && tbl ? `${base ? base + "/" : ""}${tbl}` : base);
    const path = `s3a://${dest.target_bucket}/${prefix ? prefix + "/" : ""}`;
    env.push(
      `TARGET_BUCKET=${dest.target_bucket ?? ""}`,
      `TARGET_PREFIX=${prefix}`,
      `TARGET_PATH=${path}`,
      `TARGET_LAYER=${dest.target_layer ?? ""}`,
      `FILE_FORMAT=${dest.file_format ?? "parquet"}`,
      `WRITE_MODE=${dest.write_mode}`,
      ...(dest.compression ? [`COMPRESSION=${dest.compression}`] : []),
      ...((dest.partition_columns ?? []).length ? [`PARTITION_COLUMNS=${(dest.partition_columns ?? []).join(",")}`] : []),
    );
  } else {
    const table = dest.target_table ? sub(dest.target_table, tbl) : tbl;
    const staging = dest.staging_table ? sub(dest.staging_table, tbl) : (dest.is_template && dest.write_mode === "upsert" ? `stg_${tbl}` : "");
    env.push(
      `TARGET_SCHEMA=${dest.target_schema ?? ""}`,
      `TARGET_TABLE=${table}`,
      `WRITE_MODE=${dest.write_mode}`,
      ...((dest.primary_key_columns ?? []).length ? [`PRIMARY_KEY_COLUMNS=${(dest.primary_key_columns ?? []).join(",")}`] : []),
      ...(staging ? [`STAGING_TABLE=${staging}`] : []),
      ...(dest.upsert_strategy ? [`UPSERT_STRATEGY=${dest.upsert_strategy}`] : []),
      "TARGET_HOST=…  TARGET_DB=…  TARGET_USER=…  TARGET_PASSWORD=***  (injetados da conexão)",
    );
  }

  const refJob = dest.is_template
    ? `# No Job: selecione este destino (destination_id=${dest.id}).\n# A tabela vem do Controle de Ingestão (nome_tabela) ou de um argumento:\n--table ${example}`
    : `# No Job: selecione este destino (destination_id=${dest.id}). Alvo fixo — nada a informar.`;

  const refControl = `-- Controle de Ingestão: aponte a linha da tabela para este destino\nnome_tabela = ${dest.is_template ? example : (dest.target_table ?? "…")}\ndestination_id = ${dest.id}`;

  const py = isS3
    ? `import os\nfrom pyspark.sql import functions as F\n\npath = os.environ["TARGET_PATH"]        # ${isS3 ? `s3a://${dest.target_bucket}/${dest.is_template ? "…/<tabela>" : ""}` : ""}\nmode = os.environ.get("WRITE_MODE", "append")\nparts = [c for c in os.environ.get("PARTITION_COLUMNS","").split(",") if c]\n\n(df.write.mode(mode).format(os.environ.get("FILE_FORMAT","parquet"))\n   .option("compression", os.environ.get("COMPRESSION","snappy"))\n   ${"" }.partitionBy(*parts).save(path))`
    : `import os\n\nschema = os.environ["TARGET_SCHEMA"]\ntable  = os.environ["TARGET_TABLE"]       # resolvido do destino/tabela em runtime\nmode   = os.environ.get("WRITE_MODE","append")\nkeys   = os.environ.get("PRIMARY_KEY_COLUMNS","").split(",")\nstaging= os.environ.get("STAGING_TABLE")   # ex.: stg_${dest.is_template ? example : (dest.target_table ?? "tabela")}\n# grave via JDBC usando TARGET_HOST/TARGET_DB/TARGET_USER/TARGET_PASSWORD (injetados da conexão)`;

  return (
    <div className="space-y-4">
      <p className="text-sm text-gray-500">
        {dest.is_template
          ? "Destino template: reutilizável por várias tabelas. O nome da tabela vem em runtime (Controle de Ingestão ou --table); o runner injeta a config final por execução."
          : "Destino específico: aponta para um alvo fixo. Selecione-o no Job ou no Controle de Ingestão."}
      </p>
      <div>
        <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-gray-400">Referenciar no Job</p>
        <CodeViewer content={refJob} language="shell" />
      </div>
      <div>
        <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-gray-400">Referenciar no Controle de Ingestão</p>
        <CodeViewer content={refControl} language="sql" />
      </div>
      <div>
        <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-gray-400">
          Variáveis injetadas pelo runner {dest.is_template ? `(exemplo: tabela “${example}”)` : ""}
        </p>
        <CodeViewer content={env.join("\n")} language="shell" />
      </div>
      <div>
        <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-gray-400">Exemplo no job ({isS3 ? "Spark" : "Python/JDBC"})</p>
        <CodeViewer content={py} language="python" />
      </div>
    </div>
  );
}
