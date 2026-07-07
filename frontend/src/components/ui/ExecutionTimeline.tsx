import type { ReactNode } from "react";
import { AlertCircle, CheckCircle2, Circle, Clock, Loader2, XCircle } from "lucide-react";

import { cn } from "@/lib/cn";

export interface TimelineStep {
  id: number | string;
  title: string;
  subtitle?: string;
  status: string;
  meta?: ReactNode;
}

function stepVisual(status: string) {
  switch (status) {
    case "success":
      return { icon: <CheckCircle2 size={18} />, ring: "text-emerald-500", line: "bg-emerald-200" };
    case "running":
      return { icon: <Loader2 size={18} className="animate-spin" />, ring: "text-brand-500", line: "bg-brand-200" };
    case "failed":
      return { icon: <XCircle size={18} />, ring: "text-red-500", line: "bg-red-200" };
    case "timeout":
      return { icon: <AlertCircle size={18} />, ring: "text-amber-500", line: "bg-amber-200" };
    case "queued":
      return { icon: <Clock size={18} />, ring: "text-sky-500", line: "bg-sky-200" };
    default:
      return { icon: <Circle size={18} />, ring: "text-gray-300", line: "bg-gray-200" };
  }
}

export function ExecutionTimeline({ steps }: { steps: TimelineStep[] }) {
  if (steps.length === 0) {
    return <p className="text-sm text-gray-400">Sem steps registrados.</p>;
  }
  return (
    <ol className="relative">
      {steps.map((step, i) => {
        const v = stepVisual(step.status);
        const isLast = i === steps.length - 1;
        return (
          <li key={step.id} className="relative flex gap-4 pb-6 last:pb-0">
            {!isLast && (
              <span className={cn("absolute left-[13px] top-7 h-full w-0.5", v.line)} aria-hidden />
            )}
            <span className={cn("z-10 mt-0.5 flex h-7 w-7 items-center justify-center rounded-full bg-white ring-1 ring-inset ring-gray-200", v.ring)}>
              {v.icon}
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-2">
                <p className="text-sm font-semibold text-gray-900">{step.title}</p>
                {step.meta}
              </div>
              {step.subtitle && <p className="mt-0.5 text-xs text-gray-500">{step.subtitle}</p>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
