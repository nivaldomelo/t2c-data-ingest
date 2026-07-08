import { KeyRound } from "lucide-react";

import { cn } from "@/lib/cn";

export function VariableStatusBadge({ active }: { active: boolean }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium",
        active ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-gray-200 bg-gray-100 text-gray-600"
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", active ? "bg-emerald-500" : "bg-gray-400")} />
      {active ? "Ativa" : "Inativa"}
    </span>
  );
}

export function VariableSecretBadge({ isSecret }: { isSecret: boolean }) {
  if (!isSecret) return <span className="text-xs text-gray-400">—</span>;
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700">
      <KeyRound size={12} /> Secreta
    </span>
  );
}

export function TypeBadge({ type }: { type: string }) {
  return <span className="inline-flex rounded-md bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600">{type}</span>;
}
