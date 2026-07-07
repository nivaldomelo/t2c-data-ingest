import { Card } from "@/components/ui";
import type { JobDetail } from "@/features/jobs/types";

function Row({ label, value, mono }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-gray-50 py-2.5 last:border-0">
      <span className="text-sm text-gray-500">{label}</span>
      <span className={`text-right text-sm text-gray-800 ${mono ? "font-mono text-xs" : ""}`}>{value}</span>
    </div>
  );
}

export function JobSettingsTab({ job }: { job: JobDetail }) {
  const args = (job.arguments ?? []).map(String);
  const envKeys = Object.keys(job.env_vars ?? {});

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      <Card className="p-5">
        <h2 className="mb-3 text-sm font-semibold text-gray-900">Configuração</h2>
        <Row label="Tipo" value={job.type} />
        <Row label="Engine" value={job.engine ?? "—"} mono />
        <Row label="Cluster ID" value={job.cluster_id ?? "—"} />
        <Row label="Conexão (única)" value={job.connection_id ?? "—"} />
        <Row label="Conexão origem" value={job.source_connection_name ?? job.source_connection_id ?? "—"} />
        <Row label="Conexão destino" value={job.target_connection_name ?? job.target_connection_id ?? "—"} />
        <Row label="Timeout (s)" value={job.timeout_seconds ?? "—"} />
        <Row label="Retry" value={job.retry_count ?? 0} />
        <Row label="Classe principal" value={job.main_class ?? "—"} mono />
        <Row label="Ativo" value={job.is_active ? "Sim" : "Não"} />
      </Card>

      <Card className="p-5">
        <h2 className="mb-3 text-sm font-semibold text-gray-900">Argumentos</h2>
        {args.length === 0 ? (
          <p className="text-sm text-gray-400">Sem argumentos.</p>
        ) : (
          <pre className="overflow-x-auto rounded-lg bg-gray-50 p-3 font-mono text-xs text-gray-700">
            {args.join(" ")}
          </pre>
        )}

        <h2 className="mb-2 mt-5 text-sm font-semibold text-gray-900">Variáveis de ambiente</h2>
        {envKeys.length === 0 ? (
          <p className="text-sm text-gray-400">Nenhuma variável de ambiente.</p>
        ) : (
          <div className="space-y-1">
            {envKeys.map((k) => (
              <div key={k} className="flex justify-between gap-3 font-mono text-xs">
                <span className="text-gray-600">{k}</span>
                <span className="text-gray-400">••••••</span>
              </div>
            ))}
            <p className="pt-1 text-xs text-gray-400">Valores ocultados por segurança.</p>
          </div>
        )}
      </Card>
    </div>
  );
}
