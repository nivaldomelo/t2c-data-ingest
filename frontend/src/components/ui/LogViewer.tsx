import { useMemo, useState } from "react";
import { Check, Copy, TerminalSquare } from "lucide-react";

import { cn } from "@/lib/cn";

export interface LogLine {
  id: number | string;
  level: string;
  message: string;
  logged_at?: string | null;
}

function levelClass(level: string): string {
  switch (level.toUpperCase()) {
    case "ERROR":
      return "text-red-400";
    case "WARNING":
      return "text-amber-300";
    case "DEBUG":
      return "text-slate-500";
    default:
      return "text-slate-300";
  }
}

export function LogViewer({ lines, title = "Logs" }: { lines: LogLine[]; title?: string }) {
  const [copied, setCopied] = useState(false);

  const plain = useMemo(
    () => lines.map((l) => `[${l.level}] ${l.message}`).join("\n"),
    [lines]
  );

  async function copy() {
    try {
      await navigator.clipboard.writeText(plain);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-graphite-800 bg-graphite-950 shadow-card">
      <div className="flex items-center justify-between border-b border-white/10 px-4 py-2.5">
        <div className="flex items-center gap-2 text-sm font-medium text-slate-300">
          <TerminalSquare size={16} className="text-brand-400" />
          {title}
          <span className="ml-1 rounded-full bg-white/10 px-2 py-0.5 text-xs text-slate-400">
            {lines.length}
          </span>
        </div>
        <button
          onClick={copy}
          className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium text-slate-400 transition-colors hover:bg-white/10 hover:text-slate-200"
        >
          {copied ? <Check size={14} className="text-emerald-400" /> : <Copy size={14} />}
          {copied ? "Copiado" : "Copiar"}
        </button>
      </div>
      <div className="scrollbar-dark max-h-[28rem] overflow-auto px-4 py-3 font-mono text-[13px] leading-relaxed">
        {lines.length === 0 ? (
          <p className="py-6 text-center text-slate-500">Sem logs para esta execução.</p>
        ) : (
          lines.map((l) => (
            <div
              key={l.id}
              className={cn(
                "flex gap-3 whitespace-pre-wrap break-words border-l-2 py-0.5 pl-3",
                l.level.toUpperCase() === "ERROR"
                  ? "border-red-500/70 bg-red-500/5"
                  : "border-transparent"
              )}
            >
              <span className="select-none text-[11px] uppercase tracking-wide text-slate-600">
                {l.level}
              </span>
              <span className={levelClass(l.level)}>{l.message}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
