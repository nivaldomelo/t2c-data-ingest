import { Braces } from "lucide-react";

import { CopyCodeButton } from "@/components/ui/CodeViewer";

/** Bloco de código para payloads JSON: fundo escuro, monoespaçado, indentado, com copiar. */
export function JsonViewer({ data, label = "JSON" }: { data: unknown; label?: string }) {
  const text = typeof data === "string" ? data : JSON.stringify(data ?? null, null, 2);
  return (
    <div className="overflow-hidden rounded-xl border border-graphite-800 bg-graphite-950">
      <div className="flex items-center justify-between border-b border-white/10 px-3 py-2">
        <span className="flex items-center gap-1.5 text-xs font-medium text-slate-300">
          <Braces size={14} className="text-brand-400" /> {label}
        </span>
        <CopyCodeButton content={text} label="Copiar JSON" />
      </div>
      <pre className="scrollbar-dark max-h-[45vh] overflow-auto p-3 font-mono text-xs leading-relaxed text-slate-200">
        {text}
      </pre>
    </div>
  );
}
