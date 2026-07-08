import { cn } from "@/lib/cn";

const MAP: Record<string, string> = {
  SUCESSO: "bg-emerald-50 text-emerald-700 border-emerald-200",
  ATIVO: "bg-emerald-50 text-emerald-700 border-emerald-200",
  ERRO: "bg-red-50 text-red-700 border-red-200",
  EM_EXECUCAO: "bg-brand-50 text-brand-700 border-brand-200",
  PENDENTE: "bg-gray-100 text-gray-600 border-gray-200",
  INATIVO: "bg-gray-100 text-gray-600 border-gray-200",
  PAUSADO: "bg-amber-50 text-amber-700 border-amber-200",
};

export function IngestionControlStatusBadge({ status }: { status: string | null }) {
  if (!status) return <span className="text-xs text-gray-400">—</span>;
  const cls = MAP[status] ?? "bg-gray-100 text-gray-600 border-gray-200";
  return (
    <span className={cn("inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium", cls)}>
      {status}
    </span>
  );
}

export function AtivoBadge({ ativo }: { ativo: boolean | null }) {
  const on = !!ativo;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium",
        on ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-gray-200 bg-gray-100 text-gray-600"
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", on ? "bg-emerald-500" : "bg-gray-400")} />
      {on ? "Ativo" : "Inativo"}
    </span>
  );
}
