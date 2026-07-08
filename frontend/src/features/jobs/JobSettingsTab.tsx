import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  Braces,
  Check,
  Copy,
  Cpu,
  Database,
  FileCode2,
  Info,
  Pencil,
  Settings2,
  Tag as TagIcon,
  Terminal,
  Trash2,
} from "lucide-react";

import { api } from "@/lib/api";
import { Card, PrimaryButton, SecondaryButton, StatusBadge } from "@/components/ui";
import { TagInput } from "@/features/tags/TagInput";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/cn";
import { JOB_TYPE_LABEL, fmtDate, parseJobArguments } from "@/features/jobs/types";
import type { JobDetail } from "@/features/jobs/types";
import { JobConnectionBox } from "@/features/jobs/JobConnectionBox";

/* ── helpers ── */
function CopyButton({ text, label = "Copiar" }: { text: string; label?: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setDone(true);
          setTimeout(() => setDone(false), 1500);
        } catch {
          /* ignore */
        }
      }}
      className="inline-flex items-center gap-1.5 rounded-md border border-gray-200 bg-white px-2.5 py-1 text-xs font-medium text-gray-600 transition-colors hover:bg-gray-50 hover:text-gray-900"
    >
      {done ? <Check size={13} className="text-emerald-500" /> : <Copy size={13} />} {done ? "Copiado" : label}
    </button>
  );
}

function SectionCard({
  icon, title, action, children, danger,
}: {
  icon: React.ReactNode; title: string; action?: React.ReactNode; children: React.ReactNode; danger?: boolean;
}) {
  return (
    <Card className={cn("p-5", danger && "border-red-200 bg-red-50/40")}>
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className={cn("flex items-center gap-2 text-sm font-semibold", danger ? "text-red-800" : "text-gray-900")}>
          <span className={danger ? "text-red-500" : "text-brand-500"}>{icon}</span>
          {title}
        </h2>
        {action}
      </div>
      {children}
    </Card>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-gray-400">{label}</dt>
      <dd className="mt-1 text-sm text-gray-800">{children}</dd>
    </div>
  );
}

function Muted({ children }: { children: React.ReactNode }) {
  return <span className="text-sm text-gray-400">{children}</span>;
}

/* ── cards ── */
function JobScriptPathBlock({ path }: { path: string | null }) {
  if (!path) return <Muted>Não configurado</Muted>;
  return (
    <div className="flex items-start gap-2 rounded-lg border border-graphite-800 bg-graphite-950 px-3 py-2">
      <FileCode2 size={14} className="mt-0.5 shrink-0 text-brand-400" />
      <code className="min-w-0 flex-1 break-all font-mono text-xs text-slate-200">{path}</code>
      <div className="shrink-0"><CopyButton text={path} /></div>
    </div>
  );
}

function JobMainConfigCard({ job }: { job: JobDetail }) {
  return (
    <SectionCard icon={<Settings2 size={15} />} title="Configuração principal">
      <div className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-4">
        <Field label="Tipo do job">
          <span className="inline-flex rounded-md bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-700">
            {JOB_TYPE_LABEL[job.type] ?? job.type}
          </span>
        </Field>
        <Field label="Engine">
          {job.engine ? (
            <span className="inline-flex rounded-md bg-gray-100 px-2 py-0.5 font-mono text-xs text-gray-700">{job.engine}</span>
          ) : <Muted>Não configurado</Muted>}
        </Field>
        <Field label="Ativo"><StatusBadge status={job.is_active ? "active" : "inactive"} /></Field>
        <Field label="Classe principal">
          {job.main_class ? <span className="font-mono text-xs">{job.main_class}</span> : <Muted>Não configurado</Muted>}
        </Field>
      </div>
      <div className="mt-4">
        <dt className="mb-1 text-xs font-medium uppercase tracking-wide text-gray-400">Script principal</dt>
        <JobScriptPathBlock path={job.script_path} />
      </div>
    </SectionCard>
  );
}

function JobExecutionConfigCard({ job }: { job: JobDetail }) {
  const modo = job.engine === "spark_cluster" ? "Spark cluster" : job.engine === "python_worker" ? "Python worker" : (job.engine ?? "Não configurado");
  return (
    <SectionCard icon={<Cpu size={15} />} title="Execução">
      <div className="grid grid-cols-2 gap-x-6 gap-y-4">
        <Field label="Cluster ID">{job.cluster_id ?? <Muted>Não configurado</Muted>}</Field>
        <Field label="Timeout">{job.timeout_seconds ? `${job.timeout_seconds}s` : <Muted>Sem limite definido</Muted>}</Field>
        <Field label="Retry">{job.retry_count > 0 ? `${job.retry_count} tentativa(s)` : <Muted>Nenhuma tentativa extra</Muted>}</Field>
        <Field label="Modo de execução">{modo}</Field>
      </div>
    </SectionCard>
  );
}

function JobConnectionsConfigCard({ job }: { job: JobDetail }) {
  const none = !job.source_connection && !job.target_connection && !job.connection;
  return (
    <SectionCard icon={<Database size={15} />} title="Conexões">
      {none ? (
        <Muted>Nenhuma conexão configurada</Muted>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {job.connection && <JobConnectionBox role="Conexão única" c={job.connection} />}
          <JobConnectionBox role="Origem" c={job.source_connection} />
          <JobConnectionBox role="Destino" c={job.target_connection} />
        </div>
      )}
    </SectionCard>
  );
}

function JobArgumentsCard({ job }: { job: JobDetail }) {
  const { raw, lines, pairs } = parseJobArguments(job.arguments);
  const [structured, setStructured] = useState(false);
  if (!raw) {
    return (
      <SectionCard icon={<Terminal size={15} />} title="Argumentos do job">
        <Muted>Nenhum argumento configurado</Muted>
      </SectionCard>
    );
  }
  return (
    <SectionCard
      icon={<Terminal size={15} />}
      title="Argumentos do job"
      action={
        <div className="flex items-center gap-2">
          <button onClick={() => setStructured((v) => !v)}
            className="inline-flex items-center gap-1.5 rounded-md border border-gray-200 bg-white px-2.5 py-1 text-xs font-medium text-gray-600 hover:bg-gray-50">
            <Braces size={13} /> {structured ? "Ver comando" : "Ver estruturado"}
          </button>
          <CopyButton text={raw} label="Copiar argumentos" />
        </div>
      }
    >
      {structured ? (
        <div className="divide-y divide-gray-100 rounded-lg border border-gray-100">
          {pairs.map((p) => (
            <div key={p.key} className="flex items-center justify-between gap-4 px-3 py-2 text-sm">
              <span className="font-mono text-xs text-gray-500">{p.key}</span>
              <span className="truncate font-mono text-xs text-gray-800">{p.value}</span>
            </div>
          ))}
        </div>
      ) : (
        <pre className="overflow-x-auto rounded-lg border border-graphite-800 bg-graphite-950 p-3 font-mono text-xs leading-relaxed text-slate-200">
{lines.map((l, i) => `${l}${i < lines.length - 1 ? " \\" : ""}`).join("\n")}
        </pre>
      )}
    </SectionCard>
  );
}

function JobEnvironmentVariablesCard({ job }: { job: JobDetail }) {
  const navigate = useNavigate();
  const entries = Object.entries(job.env_vars ?? {});
  return (
    <SectionCard
      icon={<Braces size={15} />}
      title="Variáveis de ambiente"
      action={<SecondaryButton size="sm" onClick={() => navigate("/variables")}>Vincular variável</SecondaryButton>}
    >
      {entries.length === 0 ? (
        <Muted>Nenhuma variável de ambiente configurada para este job.</Muted>
      ) : (
        <div className="space-y-1">
          {entries.map(([k]) => (
            <div key={k} className="flex items-center justify-between gap-3 rounded-md bg-gray-50 px-3 py-1.5 font-mono text-xs">
              <span className="text-gray-700">{k}</span>
              <span className="text-gray-400">••••••</span>
            </div>
          ))}
          <p className="pt-1 text-xs text-gray-400">Valores ocultados por segurança.</p>
        </div>
      )}
    </SectionCard>
  );
}

function JobTagsCard({ job, canTags }: { job: JobDetail; canTags: boolean }) {
  const qc = useQueryClient();
  const [tags, setTags] = useState<string[]>((job.tags ?? []).map((t) => t.name));
  const [saved, setSaved] = useState(false);
  const save = useMutation({
    mutationFn: () => api.put(`/api/v1/jobs/${job.id}/tags`, { tags }),
    onSuccess: () => {
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
      qc.invalidateQueries({ queryKey: ["job", job.id] });
      qc.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
  return (
    <SectionCard icon={<TagIcon size={15} />} title="Tags">
      <p className="mb-3 text-sm text-gray-500">Use tags para facilitar a busca e a organização dos jobs.</p>
      <TagInput value={tags} onChange={setTags} allowCreate={canTags} disabled={!canTags} placeholder="Adicionar tag e Enter…" />
      {canTags ? (
        <div className="mt-3 flex items-center gap-3">
          <PrimaryButton size="sm" loading={save.isPending} onClick={() => save.mutate()}>Salvar tags</PrimaryButton>
          {saved && <span className="inline-flex items-center gap-1 text-xs text-emerald-600"><Check size={13} /> Tags salvas.</span>}
        </div>
      ) : (
        <p className="mt-2 text-xs text-gray-400">Você não tem permissão para editar tags.</p>
      )}
    </SectionCard>
  );
}

function JobMetadataCard({ job }: { job: JobDetail }) {
  return (
    <SectionCard icon={<Info size={15} />} title="Metadados">
      <div className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3">
        <Field label="ID do job"><span className="font-mono text-xs">#{job.id}</span></Field>
        <Field label="Criado em">{fmtDate(job.created_at)}</Field>
        <Field label="Criado por">{job.created_by ?? <Muted>—</Muted>}</Field>
        <Field label="Atualizado em">{fmtDate(job.updated_at)}</Field>
        <Field label="Atualizado por">{job.updated_by ?? <Muted>—</Muted>}</Field>
      </div>
    </SectionCard>
  );
}

function JobDangerZoneCard({ onDelete }: { onDelete: () => void }) {
  return (
    <SectionCard icon={<AlertTriangle size={15} />} title="Zona de perigo" danger>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm font-medium text-gray-900">Excluir job</p>
          <p className="mt-0.5 text-sm text-gray-500">
            Remove este job da listagem ativa e arquiva o código associado em uma pasta de arquivo do projeto.
          </p>
        </div>
        <button
          onClick={onDelete}
          className="inline-flex h-10 shrink-0 items-center justify-center gap-2 rounded-lg border border-red-300 bg-white px-4 text-sm font-semibold text-red-600 transition-colors hover:bg-red-50"
        >
          <Trash2 size={15} /> Excluir job
        </button>
      </div>
    </SectionCard>
  );
}

/* ── main ── */
export function JobSettingsTab({
  job, canEdit, canDelete, onEdit, onDelete,
}: {
  job: JobDetail;
  canEdit: boolean;
  canDelete: boolean;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const { can } = useAuth();
  const canTags = can("ingest:jobs:tags:write");

  return (
    <div className="space-y-6">
      {/* header da aba */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-lg font-bold text-gray-900">Configurações do job</h1>
          <p className="mt-0.5 text-sm text-gray-500">
            Gerencie parâmetros técnicos, conexões, argumentos, variáveis e tags deste job.
          </p>
        </div>
        {canEdit && (
          <PrimaryButton icon={<Pencil size={15} />} onClick={onEdit}>Editar configurações</PrimaryButton>
        )}
      </div>

      <JobMainConfigCard job={job} />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <JobExecutionConfigCard job={job} />
        <JobConnectionsConfigCard job={job} />
      </div>

      <JobArgumentsCard job={job} />
      <JobEnvironmentVariablesCard job={job} />
      <JobTagsCard job={job} canTags={canTags} />
      <JobMetadataCard job={job} />
      {canDelete && <JobDangerZoneCard onDelete={onDelete} />}
    </div>
  );
}
