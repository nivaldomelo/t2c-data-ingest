import { useDeferredValue, useMemo, useState } from "react";
import {
  Check,
  Copy,
  Download,
  Hash,
  Maximize2,
  Minimize2,
  Search,
  TerminalSquare,
  WrapText,
  X,
} from "lucide-react";

import { cn } from "@/lib/cn";

export interface ExecLogLine {
  id: number | string;
  level: string;
  message: string;
}

// Content-based tone: applied to the message text without altering the content itself.
function messageTone(message: string, level: string): string {
  const m = message.toLowerCase();
  if (/\b(error|erro|failed|falha|exception|traceback)\b/.test(m) || level.toUpperCase() === "ERROR")
    return "text-red-400";
  if (message.includes("INGEST_SUMMARY")) return "text-brand-300 font-medium";
  if (/\b(ok|sucesso|success)\b/.test(m)) return "text-emerald-300";
  if (/\b(warning|warn)\b/.test(m) || level.toUpperCase() === "WARNING") return "text-amber-300";
  if (m.includes("spark-submit") || m.startsWith("$ ")) return "text-sky-300";
  if (message.startsWith("[pg2mysql]")) return "text-slate-200";
  return "text-slate-300";
}

function escapeRe(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

// Highlight search matches inside a line without touching the underlying text.
function renderMessage(message: string, query: string) {
  if (!query.trim()) return message;
  const parts = message.split(new RegExp(`(${escapeRe(query)})`, "ig"));
  return parts.map((p, i) =>
    p.toLowerCase() === query.toLowerCase() ? (
      <mark key={i} className="rounded bg-brand-500/40 text-white">{p}</mark>
    ) : (
      <span key={i}>{p}</span>
    )
  );
}

export function ExecutionLogViewer({
  lines,
  title = "Logs da execução",
  fileName = "execucao.log",
  running = false,
}: {
  lines: ExecLogLine[];
  title?: string;
  fileName?: string;
  running?: boolean;
}) {
  const [query, setQuery] = useState("");
  const [wrap, setWrap] = useState(true);
  const [numbers, setNumbers] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const [copied, setCopied] = useState(false);

  const deferredQuery = useDeferredValue(query);
  const plain = useMemo(() => lines.map((l) => l.message).join("\n"), [lines]);

  const visible = useMemo(() => {
    const q = deferredQuery.trim().toLowerCase();
    if (!q) return lines;
    return lines.filter((l) => l.message.toLowerCase().includes(q));
  }, [lines, deferredQuery]);

  async function copy() {
    try {
      await navigator.clipboard.writeText(plain);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* ignore */
    }
  }

  function download() {
    const blob = new Blob([plain], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = fileName;
    a.click();
    URL.revokeObjectURL(url);
  }

  const body = (
    <div
      className={cn(
        "overflow-hidden rounded-2xl border border-graphite-800 bg-graphite-950 shadow-card",
        fullscreen && "flex h-full flex-col rounded-none border-0"
      )}
    >
      {/* toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/10 px-4 py-2.5">
        <div className="flex items-center gap-2 text-sm font-medium text-slate-300">
          <TerminalSquare size={16} className="text-brand-400" />
          {title}
          <span className="ml-1 rounded-full bg-white/10 px-2 py-0.5 text-xs text-slate-400">
            {visible.length}{visible.length !== lines.length ? `/${lines.length}` : ""}
          </span>
          {running && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-brand-500/15 px-2 py-0.5 text-xs font-medium text-brand-300">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand-400" /> em execução
            </span>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <div className="relative">
            <Search size={13} className="pointer-events-none absolute left-2 top-1/2 -translate-y-1/2 text-slate-500" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Buscar…"
              className="h-7 w-40 rounded-md border border-white/10 bg-graphite-900 pl-7 pr-2 text-xs text-slate-200 outline-none placeholder:text-slate-600 focus:border-brand-500"
            />
          </div>
          <ToolbarBtn active={wrap} onClick={() => setWrap((v) => !v)} title="Quebrar linhas"><WrapText size={14} /></ToolbarBtn>
          <ToolbarBtn active={numbers} onClick={() => setNumbers((v) => !v)} title="Numerar linhas"><Hash size={14} /></ToolbarBtn>
          <ToolbarBtn onClick={copy} title="Copiar">{copied ? <Check size={14} className="text-emerald-400" /> : <Copy size={14} />}</ToolbarBtn>
          <ToolbarBtn onClick={download} title="Baixar logs"><Download size={14} /></ToolbarBtn>
          <ToolbarBtn onClick={() => setFullscreen((v) => !v)} title={fullscreen ? "Sair da tela cheia" : "Tela cheia"}>
            {fullscreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
          </ToolbarBtn>
        </div>
      </div>

      {/* terminal body */}
      <div
        className={cn(
          "scrollbar-dark overflow-auto px-2 py-3 font-mono text-[13px] leading-relaxed",
          fullscreen ? "flex-1" : "min-h-[500px] max-h-[70vh]"
        )}
      >
        {visible.length === 0 ? (
          <p className="py-10 text-center text-slate-500">
            {lines.length === 0 ? "Sem logs para esta execução." : "Nenhuma linha corresponde à busca."}
          </p>
        ) : (
          visible.map((l, i) => (
            <div
              key={l.id}
              className={cn(
                "flex gap-3 border-l-2 py-0.5 pl-2",
                l.level.toUpperCase() === "ERROR" ? "border-red-500/70 bg-red-500/5" : "border-transparent",
                wrap ? "whitespace-pre-wrap break-words" : "whitespace-pre"
              )}
            >
              {numbers && (
                <span className="w-8 shrink-0 select-none text-right text-[11px] text-slate-600">{i + 1}</span>
              )}
              <span className={cn("min-w-0", messageTone(l.message, l.level))}>
                {renderMessage(l.message, deferredQuery)}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );

  if (fullscreen) {
    return (
      <div className="fixed inset-0 z-50 flex flex-col bg-graphite-950 p-3">
        <div className="mb-2 flex justify-end">
          <button onClick={() => setFullscreen(false)} className="rounded-lg p-1.5 text-slate-400 hover:bg-white/10 hover:text-white">
            <X size={18} />
          </button>
        </div>
        <div className="min-h-0 flex-1">{body}</div>
      </div>
    );
  }
  return body;
}

function ToolbarBtn({ children, onClick, title, active }: { children: React.ReactNode; onClick: () => void; title: string; active?: boolean }) {
  return (
    <button
      onClick={onClick}
      title={title}
      className={cn(
        "inline-flex h-7 w-7 items-center justify-center rounded-md transition-colors",
        active ? "bg-brand-500/20 text-brand-300" : "text-slate-400 hover:bg-white/10 hover:text-slate-200"
      )}
    >
      {children}
    </button>
  );
}
