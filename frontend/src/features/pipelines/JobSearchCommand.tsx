import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Boxes, Search, Zap } from "lucide-react";

import { api } from "@/lib/api";
import { cn } from "@/lib/cn";

export interface JobSearchResult {
  id: number;
  name: string;
  description: string | null;
  job_type: string;
  engine: string | null;
  active: boolean;
}

/** Command-palette style autocomplete to add a job to the pipeline canvas. */
export function JobSearchCommand({
  open,
  title = "Adicionar job",
  onSelect,
  onClose,
}: {
  open: boolean;
  title?: string;
  onSelect: (job: JobSearchResult) => void;
  onClose: () => void;
}) {
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setQ("");
      setActive(0);
      setTimeout(() => inputRef.current?.focus(), 30);
    }
  }, [open]);

  const { data } = useQuery({
    queryKey: ["jobs-search", q],
    queryFn: () => api.get<JobSearchResult[]>(`/api/v1/jobs/search?limit=12${q.trim() ? `&search=${encodeURIComponent(q.trim())}` : ""}`),
    enabled: open,
  });
  const results = useMemo(() => data ?? [], [data]);

  useEffect(() => { setActive(0); }, [q]);

  if (!open) return null;

  function choose(job: JobSearchResult) {
    onSelect(job);
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, results.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
    else if (e.key === "Enter") { e.preventDefault(); if (results[active]) choose(results[active]); }
    else if (e.key === "Escape") { e.preventDefault(); onClose(); }
  }

  return (
    <div className="absolute inset-0 z-40 flex items-start justify-center bg-black/20 pt-24" onMouseDown={onClose}>
      <div className="w-[32rem] max-w-[90%] overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-card-hover" onMouseDown={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2 border-b border-gray-100 px-4 py-3">
          <Search size={16} className="text-gray-400" />
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder={`${title}…`}
            className="w-full bg-transparent text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none"
          />
          <kbd className="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] text-gray-500">Esc</kbd>
        </div>
        <div className="max-h-80 overflow-y-auto p-1.5">
          {results.length === 0 ? (
            <div className="px-3 py-6 text-center text-sm text-gray-400">Nenhum job encontrado.</div>
          ) : (
            results.map((j, i) => {
              const isSpark = j.job_type?.startsWith("spark");
              return (
                <button
                  key={j.id}
                  onMouseEnter={() => setActive(i)}
                  onClick={() => choose(j)}
                  className={cn("flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left", i === active ? "bg-brand-50" : "hover:bg-gray-50")}
                >
                  <span className={cn("flex h-8 w-8 shrink-0 items-center justify-center rounded-lg", isSpark ? "bg-brand-50 text-brand-600" : "bg-slate-100 text-slate-600")}>
                    {isSpark ? <Zap size={16} /> : <Boxes size={16} />}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium text-gray-900">{j.name}</div>
                    <div className="flex items-center gap-1.5 text-[11px] text-gray-400">
                      <span className="rounded bg-gray-100 px-1 py-0.5 text-gray-600">{j.job_type}</span>
                      {j.engine && <span>· {j.engine}</span>}
                      <span className={j.active ? "text-emerald-600" : "text-gray-400"}>· {j.active ? "ativo" : "inativo"}</span>
                    </div>
                    {j.description && <div className="truncate text-[11px] text-gray-400">{j.description}</div>}
                  </div>
                </button>
              );
            })
          )}
        </div>
        <div className="border-t border-gray-100 px-4 py-1.5 text-[11px] text-gray-400">↑↓ navegar · Enter selecionar · Esc fechar</div>
      </div>
    </div>
  );
}
