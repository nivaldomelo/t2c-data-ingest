import { CheckCircle2, XCircle } from "lucide-react";

import { cn } from "@/lib/cn";
import type { ConnectionTestResult as Result } from "@/features/connections/types";

export function ConnectionTestResult({ result }: { result: Result | null }) {
  if (!result) return null;
  const ok = result.status === "success";
  return (
    <div
      className={cn(
        "flex items-start gap-2 rounded-lg border px-3.5 py-2.5 text-sm",
        ok ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-red-200 bg-red-50 text-red-700"
      )}
    >
      {ok ? <CheckCircle2 size={16} className="mt-0.5 shrink-0" /> : <XCircle size={16} className="mt-0.5 shrink-0" />}
      <span>{result.message}</span>
    </div>
  );
}
