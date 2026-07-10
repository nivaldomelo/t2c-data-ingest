import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  CheckCircle2,
  FolderOpen,
  Loader2,
  Lock,
  RefreshCw,
  Terminal,
  XCircle,
} from "lucide-react";

import { CodeViewer } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/cn";
import { ConnectionStatusBadge } from "@/features/connections/ConnectionStatusBadge";
import type {
  Connection,
  S3ExtraParams,
  S3ObjectsOut,
  S3TestResult,
} from "@/features/connections/types";
import { S3_AUTH_MODE_LABEL } from "@/features/connections/types";

type Tab = "resumo" | "teste" | "objetos" | "como-usar";

const TABS: { id: Tab; label: string; icon: typeof CheckCircle2 }[] = [
  { id: "resumo", label: "Resumo", icon: CheckCircle2 },
  { id: "teste", label: "Teste", icon: RefreshCw },
  { id: "objetos", label: "Objetos", icon: FolderOpen },
  { id: "como-usar", label: "Como usar", icon: Terminal },
];

function fmtSize(n: number | null): string {
  if (n == null) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`;
  return `${(n / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

export function S3ConnectionDetail({ conn }: { conn: Connection }) {
  const [tab, setTab] = useState<Tab>("resumo");
  const ep = (conn.extra_params ?? {}) as S3ExtraParams;
  return (
    <div>
      <div className="flex gap-1 border-b border-gray-100">
        {TABS.map((t) => {
          const Icon = t.icon;
          const activeTab = tab === t.id;
          return (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={cn(
                "-mb-px flex items-center gap-1.5 border-b-2 px-3 py-2 text-sm font-medium transition-colors",
                activeTab
                  ? "border-brand-500 text-brand-600"
                  : "border-transparent text-gray-500 hover:text-gray-700",
              )}
            >
              <Icon size={15} />
              {t.label}
            </button>
          );
        })}
      </div>

      <div className="pt-4">
        {tab === "resumo" && <ResumoTab conn={conn} ep={ep} />}
        {tab === "teste" && <TesteTab conn={conn} />}
        {tab === "objetos" && <ObjetosTab conn={conn} ep={ep} />}
        {tab === "como-usar" && <ComoUsarTab conn={conn} ep={ep} />}
      </div>
    </div>
  );
}

function Detail({ label, value, mono }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-gray-400">{label}</dt>
      <dd className={`mt-0.5 text-gray-800 ${mono ? "font-mono text-xs break-all" : ""}`}>{value}</dd>
    </div>
  );
}

function ResumoTab({ conn, ep }: { conn: Connection; ep: S3ExtraParams }) {
  const authMode = (ep.auth_mode ?? "access_key") as keyof typeof S3_AUTH_MODE_LABEL;
  const creds =
    authMode === "access_key"
      ? conn.has_aws_access_key
        ? "Access key cadastrada (nunca exibida)"
        : "Nenhuma chave cadastrada"
      : "Provida pelo ambiente/role (sem chave armazenada)";
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
      <Detail label="Último teste" value={<ConnectionStatusBadge status={conn.last_test_status} />} />
      <Detail label="Ativo" value={conn.active ? "Sim" : "Não"} />
      <Detail label="Bucket" value={ep.bucket_name ?? "—"} mono />
      <Detail label="Região" value={ep.aws_region ?? "—"} />
      <Detail label="Prefixo base" value={ep.base_prefix || "(raiz)"} mono />
      <Detail label="Camada padrão" value={ep.default_layer ?? "—"} />
      <Detail label="Autenticação" value={S3_AUTH_MODE_LABEL[authMode] ?? authMode} />
      <Detail label="Endpoint" value={ep.endpoint_url || "AWS padrão"} mono />
      <Detail label="SSL / HTTPS" value={ep.ssl_enabled === false ? "Desabilitado" : "Habilitado"} />
      <Detail
        label="Permissões"
        value={
          <span className="flex gap-1.5">
            <span className={cn("rounded px-1.5 py-0.5 text-xs font-semibold", conn.can_read ? "bg-sky-50 text-sky-700" : "bg-gray-100 text-gray-400")}>Leitura</span>
            <span className={cn("rounded px-1.5 py-0.5 text-xs font-semibold", conn.can_write ? "bg-amber-50 text-amber-700" : "bg-gray-100 text-gray-400")}>Escrita</span>
          </span>
        }
      />
      <div className="col-span-2">
        <Detail label="Credenciais" value={<span className="inline-flex items-center gap-1.5 text-gray-600"><Lock size={13} /> {creds}</span>} />
      </div>
      {conn.last_test_message && (
        <div className="col-span-2">
          <Detail label="Mensagem do teste" value={conn.last_test_message} />
        </div>
      )}
    </dl>
  );
}

function ResultCard({ result }: { result: S3TestResult }) {
  const d = result.details ?? {};
  const flags: [string, boolean | undefined][] = [
    ["Listar (ListBucket)", d.can_list],
    ["Ler (GetObject)", d.can_read],
    ["Escrever (PutObject)", d.can_write],
  ];
  return (
    <div className={cn("rounded-xl border p-3", result.success ? "border-emerald-200 bg-emerald-50" : "border-red-200 bg-red-50")}>
      <div className="flex items-center gap-2 text-sm font-medium">
        {result.success ? <CheckCircle2 size={16} className="text-emerald-600" /> : <XCircle size={16} className="text-red-600" />}
        <span className={result.success ? "text-emerald-800" : "text-red-800"}>{result.message}</span>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {flags.map(([label, ok]) => (
          <span key={label} className={cn("rounded-full px-2.5 py-0.5 text-xs font-medium", ok ? "bg-white text-emerald-700 ring-1 ring-emerald-200" : "bg-white/60 text-gray-500 ring-1 ring-gray-200")}>
            {ok ? "✓" : "—"} {label}
          </span>
        ))}
      </div>
    </div>
  );
}

function TesteTab({ conn }: { conn: Connection }) {
  const { can } = useAuth();
  const canRead = can("ingest:s3:read");
  const canWrite = can("ingest:s3:write");

  const readTest = useMutation({
    mutationFn: () => api.post<S3TestResult>(`/api/v1/connections/${conn.id}/s3/test-read`, {}),
  });
  const writeTest = useMutation({
    mutationFn: () => api.post<S3TestResult>(`/api/v1/connections/${conn.id}/s3/test-write`, {}),
  });

  return (
    <div className="space-y-4">
      <p className="text-sm text-gray-500">
        O teste valida credenciais, região e bucket. A escrita grava um objeto temporário em
        <span className="mx-1 font-mono text-xs">_t2c_connection_tests/</span> e o remove em seguida — nenhum outro dado é alterado.
      </p>
      <div className="flex flex-wrap gap-2">
        <button
          disabled={!canRead || readTest.isPending}
          onClick={() => readTest.mutate()}
          className="inline-flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
        >
          {readTest.isPending ? <Loader2 size={15} className="animate-spin" /> : <RefreshCw size={15} />}
          Testar leitura
        </button>
        <button
          disabled={!canWrite || !conn.can_write || writeTest.isPending}
          title={!conn.can_write ? "Escrita não habilitada nesta conexão" : undefined}
          onClick={() => writeTest.mutate()}
          className="inline-flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm font-medium text-amber-800 hover:bg-amber-100 disabled:opacity-50"
        >
          {writeTest.isPending ? <Loader2 size={15} className="animate-spin" /> : <RefreshCw size={15} />}
          Testar escrita
        </button>
      </div>
      {readTest.data && <ResultCard result={readTest.data} />}
      {readTest.error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{(readTest.error as Error).message}</p>}
      {writeTest.data && <ResultCard result={writeTest.data} />}
      {writeTest.error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{(writeTest.error as Error).message}</p>}
    </div>
  );
}

function ObjetosTab({ conn, ep }: { conn: Connection; ep: S3ExtraParams }) {
  const { can } = useAuth();
  const canList = can("ingest:s3:list");
  const [prefix, setPrefix] = useState(ep.base_prefix ?? "");
  const listing = useMutation({
    mutationFn: (pfx: string) =>
      api.get<S3ObjectsOut>(`/api/v1/connections/${conn.id}/s3/objects?limit=100&prefix=${encodeURIComponent(pfx)}`),
  });

  if (!canList) {
    return <p className="text-sm text-gray-500">Você não tem permissão para listar objetos (ingest:s3:list).</p>;
  }

  const items = listing.data?.items ?? [];
  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        <input
          value={prefix}
          onChange={(e) => setPrefix(e.target.value)}
          placeholder="Prefixo (ex.: bronze/vendas)"
          className="h-9 flex-1 rounded-lg border border-gray-200 px-3 text-sm focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
          onKeyDown={(e) => e.key === "Enter" && listing.mutate(prefix)}
        />
        <button
          onClick={() => listing.mutate(prefix)}
          disabled={listing.isPending}
          className="inline-flex items-center gap-2 rounded-lg bg-brand-500 px-3 py-2 text-sm font-medium text-white hover:bg-brand-600 disabled:opacity-50"
        >
          {listing.isPending ? <Loader2 size={15} className="animate-spin" /> : <FolderOpen size={15} />}
          Listar
        </button>
      </div>
      {listing.error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{(listing.error as Error).message}</p>}
      {listing.data && (
        <div className="overflow-hidden rounded-xl border border-gray-100">
          <div className="max-h-72 overflow-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-gray-50 text-left text-xs uppercase tracking-wide text-gray-400">
                <tr>
                  <th className="px-3 py-2 font-medium">Objeto</th>
                  <th className="px-3 py-2 text-right font-medium">Tamanho</th>
                  <th className="px-3 py-2 text-right font-medium">Modificado</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {items.map((o) => (
                  <tr key={o.key}>
                    <td className="px-3 py-1.5 font-mono text-xs text-gray-700">{o.key}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums text-gray-500">{fmtSize(o.size)}</td>
                    <td className="px-3 py-1.5 text-right text-xs text-gray-400">
                      {o.last_modified ? new Date(o.last_modified).toLocaleString("pt-BR") : "—"}
                    </td>
                  </tr>
                ))}
                {items.length === 0 && (
                  <tr>
                    <td colSpan={3} className="px-3 py-6 text-center text-sm text-gray-400">
                      Nenhum objeto neste prefixo.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function ComoUsarTab({ conn, ep }: { conn: Connection; ep: S3ExtraParams }) {
  const bucket = ep.bucket_name ?? "meu-bucket";
  const prefix = ep.base_prefix ? ep.base_prefix.replace(/\/$/, "") : "";
  const table = "clientes";
  const base = prefix ? `${prefix}/${table}` : table;
  const s3aPath = `s3a://${bucket}/${base}/ano=2026/mes=07/dia=09/`;
  const role = conn.name.toUpperCase().replace(/[^A-Z0-9]/g, "_");

  const python = `# Job Python — usa o helper baked e as credenciais que o worker injeta por role.
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _lib.t2c_s3 import s3_client_from_env, s3_path_for_role

# Referencie a conexão no job:  --target-connection ${conn.name}
s3 = s3_client_from_env("TARGET")            # boto3, já apontando p/ endpoint/região
print(s3_path_for_role("${table}", "TARGET"))  # ${s3aPath.replace("s3a://", "s3://")}

# Exemplo: listar objetos
resp = s3.list_objects_v2(Bucket="${bucket}", Prefix="${base}/")
for o in resp.get("Contents", []):
    print(o["Key"], o["Size"])`;

  const spark = `# Job Spark — o worker injeta os --conf s3a e as credenciais via env (nunca na linha de comando).
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _lib.t2c_s3 import build_s3_path
from pyspark.sql import SparkSession

spark = SparkSession.builder.appName("ingest-${table}").getOrCreate()

# Referencie a conexão no job:  --target-connection ${conn.name}
path = build_s3_path("${bucket}", "${prefix}", "${table}")   # ${s3aPath}

df = spark.read.parquet("${s3aPath}")   # leitura
df.write.mode("overwrite").parquet(path)  # escrita particionada por ano/mes/dia`;

  const cli = `# No job (Spark ou Python), referencie esta conexão como origem e/ou destino:
--source-connection ${conn.name}     # leitura (${conn.can_read ? "habilitada" : "NÃO habilitada"})
--target-connection ${conn.name}     # escrita (${conn.can_write ? "habilitada" : "NÃO habilitada"})

# O worker expõe, por role:  ${role}… -> TARGET_S3_BUCKET / TARGET_S3_PREFIX / TARGET_S3_REGION …
# e AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY (ou role/instance profile) apenas via variáveis de ambiente.`;

  return (
    <div className="space-y-4">
      <p className="text-sm text-gray-500">
        Padrão de caminho: <span className="font-mono text-xs text-gray-700">s3a://{"{bucket}"}/{"{prefixo}"}/{"{tabela}"}/ano=YYYY/mes=MM/dia=DD/</span>
      </p>
      <div>
        <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-gray-400">Como referenciar no job</p>
        <CodeViewer content={cli} language="shell" />
      </div>
      <div>
        <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-gray-400">Spark (s3a)</p>
        <CodeViewer content={spark} language="python" />
      </div>
      <div>
        <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-gray-400">Python (boto3)</p>
        <CodeViewer content={python} language="python" />
      </div>
    </div>
  );
}
