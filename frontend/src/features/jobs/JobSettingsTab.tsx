import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { Card, PrimaryButton } from "@/components/ui";
import { TagInput } from "@/features/tags/TagInput";
import { useAuth } from "@/lib/auth";
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
  const { can } = useAuth();
  const qc = useQueryClient();
  const canTags = can("ingest:jobs:tags:write");
  const [tags, setTags] = useState<string[]>((job.tags ?? []).map((t) => t.name));
  const [saved, setSaved] = useState(false);
  const saveTags = useMutation({
    mutationFn: () => api.put(`/api/v1/jobs/${job.id}/tags`, { tags }),
    onSuccess: () => { setSaved(true); setTimeout(() => setSaved(false), 2500); qc.invalidateQueries({ queryKey: ["job", job.id] }); qc.invalidateQueries({ queryKey: ["jobs"] }); },
  });

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      <Card className="p-5 lg:col-span-2">
        <h2 className="mb-3 text-sm font-semibold text-gray-900">Tags</h2>
        <TagInput value={tags} onChange={setTags} allowCreate={canTags} disabled={!canTags} placeholder="Adicionar tag e Enter…" />
        {canTags && (
          <div className="mt-3 flex items-center gap-3">
            <PrimaryButton size="sm" loading={saveTags.isPending} onClick={() => saveTags.mutate()}>Salvar tags</PrimaryButton>
            {saved && <span className="text-xs text-emerald-600">Tags salvas.</span>}
          </div>
        )}
        {!canTags && <p className="mt-2 text-xs text-gray-400">Você não tem permissão para editar tags.</p>}
      </Card>
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
