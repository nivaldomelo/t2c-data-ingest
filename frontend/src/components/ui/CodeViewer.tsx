import { useMemo, useState } from "react";
import { Check, Copy, FileCode2 } from "lucide-react";

import { cn } from "@/lib/cn";

const LANG_LABEL: Record<string, string> = {
  python: "Python",
  sql: "SQL",
  shell: "Shell",
  scala: "Scala",
  spark: "Spark",
  r: "R",
  text: "Texto",
};

export function CopyCodeButton({ content, label = "Copiar código" }: { content: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* ignore */
    }
  }
  return (
    <button
      onClick={copy}
      className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium text-slate-300 transition-colors hover:bg-white/10 hover:text-white"
    >
      {copied ? <Check size={14} className="text-emerald-400" /> : <Copy size={14} />}
      {copied ? "Copiado" : label}
    </button>
  );
}

export function CodeViewer({
  content,
  language,
  path,
  readOnly = true,
}: {
  content: string;
  language: string;
  path?: string | null;
  readOnly?: boolean;
}) {
  const lines = useMemo(() => content.replace(/\n$/, "").split("\n"), [content]);
  const gutterWidth = String(lines.length).length;

  return (
    <div className="overflow-hidden rounded-2xl border border-graphite-800 bg-graphite-950 shadow-card">
      <div className="flex items-center justify-between gap-3 border-b border-white/10 px-4 py-2.5">
        <div className="flex min-w-0 items-center gap-2 text-sm text-slate-300">
          <FileCode2 size={16} className="shrink-0 text-brand-400" />
          <span className="truncate font-mono text-xs text-slate-400">{path ?? "—"}</span>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span className="rounded-full bg-brand-500/15 px-2 py-0.5 text-xs font-semibold text-brand-300">
            {LANG_LABEL[language] ?? language}
          </span>
          {readOnly && (
            <span className="rounded-full bg-white/10 px-2 py-0.5 text-xs text-slate-400">
              somente leitura
            </span>
          )}
          <CopyCodeButton content={content} />
        </div>
      </div>
      <div className="scrollbar-dark max-h-[60vh] overflow-auto">
        <table className="w-full border-collapse font-mono text-[13px] leading-relaxed">
          <tbody>
            {lines.map((line, i) => (
              <tr key={i} className="hover:bg-white/[0.03]">
                <td
                  className="select-none border-r border-white/5 px-3 text-right align-top text-slate-600"
                  style={{ width: `${gutterWidth + 2}ch` }}
                >
                  {i + 1}
                </td>
                <td className="whitespace-pre px-4 text-slate-200">
                  <code className={cn("break-words")}>{line || " "}</code>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
