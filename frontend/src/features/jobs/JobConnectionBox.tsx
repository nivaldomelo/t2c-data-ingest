import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { ExternalLink, Plug } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/cn";
import type { JobConnectionInfo } from "@/features/jobs/types";

export function JobConnectionBox({ role, c }: { role: string; c: JobConnectionInfo | null }) {
  const navigate = useNavigate();
  const { can } = useAuth();
  const [result, setResult] = useState<{ ok: boolean; msg: string } | null>(null);
  const test = useMutation({
    mutationFn: () => api.post<{ status?: string; success?: boolean; message?: string }>(`/api/v1/connections/${c?.id}/test`, {}),
    onSuccess: (r) => setResult({ ok: r.status === "success" || r.success === true, msg: r.message ?? "Teste concluído." }),
    onError: (e) => setResult({ ok: false, msg: e instanceof ApiError ? e.message : "Falha no teste." }),
  });

  if (!c) {
    return (
      <div className="rounded-xl border border-gray-100 bg-gray-50/60 p-4">
        <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-500">{role}</p>
        <span className="text-sm text-gray-400">Nenhuma conexão configurada</span>
      </div>
    );
  }
  const status = c.last_test_status ?? "not_tested";
  const testTone = status === "success" ? "text-emerald-600" : status === "failed" ? "text-red-600" : "text-gray-400";
  return (
    <div className="rounded-xl border border-gray-100 bg-gray-50/60 p-4">
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">{role}</p>
      <div className="flex items-center gap-2">
        <span className="text-sm font-semibold text-gray-900">{c.name}</span>
        {c.type && <span className="rounded bg-gray-200/70 px-1.5 py-0.5 text-[11px] font-medium uppercase text-gray-600">{c.type}</span>}
        {c.type === "s3" && (
          <span className="inline-flex gap-1">
            {c.can_read && <span className="rounded bg-sky-50 px-1.5 py-0.5 text-[10px] font-semibold text-sky-700">R</span>}
            {c.can_write && <span className="rounded bg-amber-50 px-1.5 py-0.5 text-[10px] font-semibold text-amber-700">W</span>}
          </span>
        )}
      </div>
      <p className="mt-1 break-all font-mono text-xs text-gray-500">
        {c.type === "s3"
          ? `s3://${c.bucket ?? "—"}${c.prefix ? `/${c.prefix}` : ""}${c.region ? ` · ${c.region}` : ""}`
          : `${c.host ?? "—"}${c.port ? `:${c.port}` : ""}${c.database ? `/${c.database}` : ""}`}
      </p>
      <p className={cn("mt-1 text-xs font-medium", testTone)}>
        Último teste: {status === "success" ? "sucesso" : status === "failed" ? "falhou" : "não testado"}
      </p>
      {result && <p className={cn("mt-1 text-xs", result.ok ? "text-emerald-600" : "text-red-600")}>{result.msg}</p>}
      <div className="mt-3 flex flex-wrap gap-2">
        {c.id && can("ingest:connections:test") && (
          <button onClick={() => test.mutate()} disabled={test.isPending}
            className="inline-flex items-center gap-1.5 rounded-md border border-gray-200 bg-white px-2.5 py-1 text-xs font-medium text-gray-600 hover:bg-gray-50 disabled:opacity-50">
            <Plug size={13} /> {test.isPending ? "Testando…" : "Testar conexão"}
          </button>
        )}
        <button onClick={() => navigate("/connections")}
          className="inline-flex items-center gap-1.5 rounded-md border border-gray-200 bg-white px-2.5 py-1 text-xs font-medium text-gray-600 hover:bg-gray-50">
          <ExternalLink size={13} /> Abrir conexão
        </button>
      </div>
    </div>
  );
}
