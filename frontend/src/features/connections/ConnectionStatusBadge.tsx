import { CheckCircle2, HelpCircle, XCircle } from "lucide-react";

import { cn } from "@/lib/cn";
import type { TestStatus } from "@/features/connections/types";

const MAP: Record<TestStatus, { label: string; cls: string; icon: typeof CheckCircle2 }> = {
  success: { label: "Conectado", cls: "bg-emerald-50 text-emerald-700 border-emerald-200", icon: CheckCircle2 },
  failed: { label: "Falhou", cls: "bg-red-50 text-red-700 border-red-200", icon: XCircle },
  not_tested: { label: "Não testado", cls: "bg-gray-100 text-gray-600 border-gray-200", icon: HelpCircle },
};

export function ConnectionStatusBadge({ status }: { status: TestStatus }) {
  const t = MAP[status] ?? MAP.not_tested;
  const Icon = t.icon;
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium", t.cls)}>
      <Icon size={13} />
      {t.label}
    </span>
  );
}
