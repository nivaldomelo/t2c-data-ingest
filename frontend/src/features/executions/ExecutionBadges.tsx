import { Cloud, GitBranch, Hand, RefreshCw, Timer } from "lucide-react";

import { cn } from "@/lib/cn";

const STATUS_TONE: Record<string, { text: string; bg: string; border: string; dot: string }> = {
  success: { text: "text-emerald-700", bg: "bg-emerald-50", border: "border-emerald-200", dot: "bg-emerald-500" },
  running: { text: "text-brand-700", bg: "bg-brand-50", border: "border-brand-200", dot: "bg-brand-500" },
  failed: { text: "text-red-700", bg: "bg-red-50", border: "border-red-200", dot: "bg-red-500" },
  timeout: { text: "text-amber-700", bg: "bg-amber-50", border: "border-amber-200", dot: "bg-amber-500" },
  queued: { text: "text-gray-600", bg: "bg-gray-100", border: "border-gray-200", dot: "bg-gray-400" },
  skipped: { text: "text-gray-500", bg: "bg-gray-50", border: "border-gray-200", dot: "bg-gray-300" },
  cancelled: { text: "text-gray-700", bg: "bg-gray-200/70", border: "border-gray-300", dot: "bg-gray-500" },
};

const STATUS_LABEL: Record<string, string> = {
  success: "Sucesso",
  running: "Em execução",
  failed: "Falha",
  timeout: "Timeout",
  queued: "Na fila",
  skipped: "Ignorado",
  cancelled: "Cancelado",
};

export function ExecutionStatusBadge({ status, size = "md" }: { status: string; size?: "sm" | "md" | "lg" }) {
  const tone = STATUS_TONE[status] ?? STATUS_TONE.queued;
  const label = STATUS_LABEL[status] ?? status;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border font-medium",
        tone.bg, tone.text, tone.border,
        size === "sm" && "px-2 py-0.5 text-xs",
        size === "md" && "px-2.5 py-0.5 text-sm",
        size === "lg" && "px-3.5 py-1 text-base"
      )}
    >
      <span className={cn("h-2 w-2 rounded-full", tone.dot, status === "running" && "animate-pulse")} />
      {label}
    </span>
  );
}

const TRIGGER: Record<string, { label: string; icon: typeof Hand }> = {
  manual: { label: "Manual", icon: Hand },
  schedule: { label: "Agendamento", icon: Timer },
  api: { label: "API", icon: Cloud },
  pipeline: { label: "Pipeline", icon: GitBranch },
  retry: { label: "Retry", icon: RefreshCw },
};

export function ExecutionTriggerBadge({ trigger }: { trigger: string }) {
  const t = TRIGGER[trigger] ?? { label: trigger, icon: Hand };
  const Icon = t.icon;
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-gray-200 bg-white px-2.5 py-0.5 text-xs font-medium text-gray-600">
      <Icon size={12} className="text-gray-400" /> {t.label}
    </span>
  );
}
