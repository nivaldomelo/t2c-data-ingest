import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Boxes, Database, GitBranch, History, RotateCcw, Table2 } from "lucide-react";

import { api, type Page } from "@/lib/api";
import { DataTable, EmptyState, PageHeader, PrimaryButton } from "@/components/ui";
import type { Column } from "@/components/ui";
import { cn } from "@/lib/cn";
import { useAuth } from "@/lib/auth";
import { CreateBackfillModal } from "@/features/backfill/CreateBackfillModal";

interface Backfill {
  id: number;
  kind: string;
  target_label: string | null;
  period_start: string | null;
  period_end: string | null;
  reset_watermark: boolean;
  watermarks_reset: number;
  status: string;
  total_targets: number;
  succeeded: number;
  failed: number;
  reason: string | null;
  created_by: string | null;
  created_at: string;
}

const KIND_ICON: Record<string, typeof Boxes> = { job: Boxes, pipeline: GitBranch, control_group: Database, control_table: Table2 };
const KIND_LABEL: Record<string, string> = { job: "Job", pipeline: "Pipeline", control_group: "Grupo", control_table: "Tabela" };
const STATUS: Record<string, { label: string; tone: string }> = {
  queued: { label: "Na fila", tone: "border-sky-200 bg-sky-50 text-sky-700" },
  running: { label: "Em execução", tone: "border-brand-200 bg-brand-50 text-brand-700" },
  success: { label: "Sucesso", tone: "border-emerald-200 bg-emerald-50 text-emerald-700" },
  partial: { label: "Parcial", tone: "border-amber-200 bg-amber-50 text-amber-700" },
  failed: { label: "Falha", tone: "border-red-200 bg-red-50 text-red-700" },
};

function fmt(t: string | null): string { return t ? new Date(t).toLocaleString("pt-BR") : "—"; }
function fmtDay(t: string | null): string { return t ? new Date(t + "T00:00:00").toLocaleDateString("pt-BR") : ""; }

export default function BackfillsPage() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const canRun = can("ingest:backfill:run");
  const [open, setOpen] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["backfills"],
    queryFn: () => api.get<Page<Backfill>>("/api/v1/backfills?page=1&page_size=50"),
    refetchInterval: (q) => ((q.state.data as Page<Backfill> | undefined)?.items.some((b) => ["queued", "running"].includes(b.status)) ? 3000 : false),
  });

  const columns: Column<Backfill>[] = [
    {
      key: "target", header: "Alvo", render: (b) => {
        const Icon = KIND_ICON[b.kind] ?? Boxes;
        return (
          <div className="flex items-center gap-2">
            <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-brand-50 text-brand-600"><Icon size={15} /></span>
            <div>
              <div className="font-medium text-gray-900">{b.target_label ?? "—"}</div>
              <div className="text-xs text-gray-400">{KIND_LABEL[b.kind] ?? b.kind}{b.reason ? ` · ${b.reason}` : ""}</div>
            </div>
          </div>
        );
      },
    },
    { key: "period", header: "Período", render: (b) => (b.period_start || b.period_end) ? <span className="text-xs text-gray-600">{fmtDay(b.period_start)} – {fmtDay(b.period_end)}</span> : <span className="text-xs text-gray-400">—</span> },
    { key: "targets", header: "Execuções", align: "center", render: (b) => <span className="text-sm text-gray-700">{b.succeeded}/{b.total_targets}{b.failed ? ` · ${b.failed} falha` : ""}</span> },
    { key: "wm", header: "Watermark", align: "center", render: (b) => b.watermarks_reset ? <span className="text-xs text-amber-700">{b.watermarks_reset} reset</span> : <span className="text-xs text-gray-400">—</span> },
    { key: "status", header: "Status", render: (b) => { const s = STATUS[b.status] ?? STATUS.queued; return <span className={cn("inline-flex rounded-full border px-2.5 py-0.5 text-xs font-medium", s.tone)}>{s.label}</span>; } },
    { key: "created", header: "Criado", align: "right", render: (b) => <div className="text-xs text-gray-500">{fmt(b.created_at)}<div className="text-gray-400">{b.created_by}</div></div> },
  ];

  return (
    <div>
      <PageHeader
        icon={<History size={22} />}
        title="Reprocessamentos"
        description="Reprocesse jobs, pipelines, grupos e tabelas de forma controlada e rastreável (backfill)."
        actions={canRun && <PrimaryButton icon={<RotateCcw size={16} />} onClick={() => setOpen(true)}>Novo reprocessamento</PrimaryButton>}
      />

      <DataTable
        columns={columns}
        rows={data?.items ?? []}
        rowKey={(b) => b.id}
        loading={isLoading}
        empty={
          <EmptyState
            icon={<History size={24} />}
            title="Nenhum reprocessamento"
            description="Reprocesse uma tabela, um grupo, um job ou um pipeline. Cada reprocessamento gera execuções rastreáveis."
            action={canRun ? <PrimaryButton icon={<RotateCcw size={16} />} onClick={() => setOpen(true)}>Novo reprocessamento</PrimaryButton> : undefined}
          />
        }
      />

      <CreateBackfillModal open={open} onClose={() => { setOpen(false); qc.invalidateQueries({ queryKey: ["backfills"] }); }} />
    </div>
  );
}
