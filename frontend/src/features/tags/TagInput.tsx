import { useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";

import { api } from "@/lib/api";
import type { Page } from "@/lib/api";
import { cn } from "@/lib/cn";
import type { Tag } from "@/features/tags/types";

/** Multiselect tag input with autocomplete (existing tags) + optional create-on-Enter. */
export function TagInput({
  value,
  onChange,
  allowCreate = true,
  placeholder = "Adicionar tag…",
  disabled = false,
}: {
  value: string[];
  onChange: (tags: string[]) => void;
  allowCreate?: boolean;
  placeholder?: string;
  disabled?: boolean;
}) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const { data } = useQuery({
    queryKey: ["tags-suggest", q],
    queryFn: () => api.get<Page<Tag>>(`/api/v1/tags?active=true&page=1&page_size=20${q.trim() ? `&search=${encodeURIComponent(q.trim())}` : ""}`),
    enabled: open,
  });
  const suggestions = (data?.items ?? []).filter((t) => !value.some((v) => v.toLowerCase() === t.name.toLowerCase()));

  function add(name: string) {
    const n = name.trim();
    if (!n) return;
    if (!value.some((v) => v.toLowerCase() === n.toLowerCase())) onChange([...value, n]);
    setQ("");
  }
  function remove(name: string) { onChange(value.filter((v) => v !== name)); }

  return (
    <div className="relative">
      <div className={cn("flex flex-wrap items-center gap-1.5 rounded-lg border border-gray-200 bg-white p-1.5", disabled && "opacity-60")}>
        {value.map((t) => (
          <span key={t} className="inline-flex items-center gap-1 rounded-md border border-gray-200 bg-gray-50 px-1.5 py-0.5 text-xs font-medium text-gray-700">
            {t}
            {!disabled && <button type="button" onClick={() => remove(t)} className="text-gray-400 hover:text-red-600"><X size={12} /></button>}
          </span>
        ))}
        {!disabled && (
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => { setQ(e.target.value); setOpen(true); }}
            onFocus={() => setOpen(true)}
            onBlur={() => setTimeout(() => setOpen(false), 150)}
            onKeyDown={(e) => {
              if (e.key === "Enter") { e.preventDefault(); if (allowCreate || suggestions[0]) add(allowCreate ? q : suggestions[0].name); }
              else if (e.key === "Backspace" && !q && value.length) remove(value[value.length - 1]);
            }}
            placeholder={value.length ? "" : placeholder}
            className="min-w-[8rem] flex-1 bg-transparent px-1 text-sm focus:outline-none"
          />
        )}
      </div>
      {open && (suggestions.length > 0 || (allowCreate && q.trim())) && (
        <div className="absolute z-30 mt-1 max-h-52 w-full overflow-y-auto rounded-lg border border-gray-200 bg-white p-1 shadow-card-hover">
          {suggestions.map((t) => (
            <button key={t.id} type="button" onMouseDown={(e) => { e.preventDefault(); add(t.name); }} className="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left text-sm hover:bg-brand-50">
              <span className="text-gray-800">{t.name}</span>
              <span className="text-[11px] text-gray-400">{t.jobs_count} job(s)</span>
            </button>
          ))}
          {allowCreate && q.trim() && !suggestions.some((s) => s.name.toLowerCase() === q.trim().toLowerCase()) && (
            <button type="button" onMouseDown={(e) => { e.preventDefault(); add(q); }} className="flex w-full items-center gap-1 rounded-md px-2 py-1.5 text-left text-sm text-brand-600 hover:bg-brand-50">
              Criar tag "<span className="font-medium">{q.trim()}</span>"
            </button>
          )}
        </div>
      )}
    </div>
  );
}
