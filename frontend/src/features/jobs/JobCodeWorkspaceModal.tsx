import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Editor from "@monaco-editor/react";
import {
  AlertTriangle,
  Check,
  ChevronDown,
  ChevronRight,
  FilePlus2,
  FileText,
  Folder,
  FolderOpen,
  FolderPlus,
  Lock,
  Pencil,
  RefreshCw,
  Save,
  ShieldAlert,
  Trash2,
  X,
} from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { MONACO_LANGUAGE } from "@/lib/monaco-setup";
import { cn } from "@/lib/cn";

// ── types (mirror backend schemas/workspace.py) ──
interface TreeNode {
  name: string;
  path: string;
  type: "file" | "folder";
  language?: string;
  children?: TreeNode[];
}
interface WorkspaceTree {
  job_id: number;
  workspace_path: string;
  main_path: string | null;
  editable: boolean;
  tree: TreeNode;
}
interface WorkspaceFile {
  job_id: number;
  path: string;
  file_name: string;
  language: string;
  content: string;
  last_modified_at: string | null;
  size_bytes: number | null;
  editable: boolean;
}
interface OpenFile {
  path: string;
  fileName: string;
  language: string;
  base: string;
  value: string;
  mtime: string | null;
  readOnly: boolean;
  loading: boolean;
  conflict: boolean;
}

const PERM = {
  read: "ingest:jobs:code:read",
  write: "ingest:jobs:code:write",
  create: "ingest:jobs:code:create",
  delete: "ingest:jobs:code:delete",
  rename: "ingest:jobs:code:rename",
};

const LANG_LABEL: Record<string, string> = {
  python: "Python", sql: "SQL", shell: "Shell", yaml: "YAML", json: "JSON", markdown: "Markdown", text: "Texto",
};

// Patterns that likely indicate hardcoded credentials in the code.
const CREDENTIAL_RE =
  /(password\s*=|senha\s*=|secret\s*=|token\s*=|access_key|secret_key|api_key|private_key)/i;

function fmtBytes(n: number | null): string {
  if (n == null) return "—";
  if (n < 1024) return `${n} B`;
  return `${(n / 1024).toFixed(1)} KB`;
}

// ── small inline dialogs (workspace is dark/full-bleed; the shared Modal is light) ──
function InputDialog({
  title, label, initial, confirmLabel, onSubmit, onCancel,
}: {
  title: string; label: string; initial: string; confirmLabel: string;
  onSubmit: (value: string) => void; onCancel: () => void;
}) {
  const [value, setValue] = useState(initial);
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => {
    ref.current?.focus();
    ref.current?.select();
  }, []);
  return (
    <div className="absolute inset-0 z-30 flex items-center justify-center bg-graphite-950/60 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-xl border border-white/10 bg-graphite-900 p-5 shadow-card-hover">
        <h3 className="text-sm font-semibold text-slate-100">{title}</h3>
        <label className="mt-3 block text-xs text-slate-400">{label}</label>
        <input
          ref={ref}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && value.trim()) onSubmit(value.trim());
            if (e.key === "Escape") onCancel();
          }}
          className="mt-1.5 w-full rounded-lg border border-white/10 bg-graphite-950 px-3 py-2 font-mono text-sm text-slate-100 outline-none focus:border-brand-500"
          placeholder="ex.: utils/helper.py"
        />
        <div className="mt-4 flex justify-end gap-2">
          <button onClick={onCancel} className="rounded-md px-3 py-1.5 text-xs font-medium text-slate-300 hover:bg-white/10">
            Cancelar
          </button>
          <button
            onClick={() => value.trim() && onSubmit(value.trim())}
            disabled={!value.trim()}
            className="rounded-md bg-brand-500 px-3 py-1.5 text-xs font-semibold text-white hover:bg-brand-600 disabled:opacity-50"
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

function ConfirmDialog({
  title, message, confirmLabel, danger, onConfirm, onCancel,
}: {
  title: string; message: string; confirmLabel: string; danger?: boolean;
  onConfirm: () => void; onCancel: () => void;
}) {
  return (
    <div className="absolute inset-0 z-30 flex items-center justify-center bg-graphite-950/60 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-xl border border-white/10 bg-graphite-900 p-5 shadow-card-hover">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-100">
          {danger && <AlertTriangle size={16} className="text-red-400" />} {title}
        </h3>
        <p className="mt-2 text-sm text-slate-400">{message}</p>
        <div className="mt-4 flex justify-end gap-2">
          <button onClick={onCancel} className="rounded-md px-3 py-1.5 text-xs font-medium text-slate-300 hover:bg-white/10">
            Cancelar
          </button>
          <button
            onClick={onConfirm}
            className={cn(
              "rounded-md px-3 py-1.5 text-xs font-semibold text-white",
              danger ? "bg-red-500 hover:bg-red-600" : "bg-brand-500 hover:bg-brand-600"
            )}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── file explorer ──
function TreeItem({
  node, depth, expanded, toggle, onOpen, activePath, mainPath,
  canWrite, canDelete, canRename, canCreate, onNewInside, onRename, onDelete,
}: {
  node: TreeNode; depth: number; expanded: Set<string>; toggle: (p: string) => void;
  onOpen: (n: TreeNode) => void; activePath: string | null; mainPath: string | null;
  canWrite: boolean; canDelete: boolean; canRename: boolean; canCreate: boolean;
  onNewInside: (folder: string) => void; onRename: (n: TreeNode) => void; onDelete: (n: TreeNode) => void;
}) {
  const isFolder = node.type === "folder";
  const isOpen = expanded.has(node.path);
  const isRoot = node.path === "";
  const isActive = activePath === node.path;
  const isMain = mainPath != null && node.path === mainPath;
  const pad = 8 + depth * 12;

  return (
    <div>
      <div
        className={cn(
          "group flex items-center gap-1 py-1 pr-1 text-sm",
          isActive ? "bg-brand-500/15 text-brand-200" : "text-slate-300 hover:bg-white/5"
        )}
        style={{ paddingLeft: pad }}
      >
        <button
          className="flex min-w-0 flex-1 items-center gap-1.5 text-left"
          onClick={() => (isFolder ? toggle(node.path) : onOpen(node))}
        >
          {isFolder ? (
            <>
              {isOpen ? <ChevronDown size={14} className="shrink-0 text-slate-500" /> : <ChevronRight size={14} className="shrink-0 text-slate-500" />}
              {isOpen ? <FolderOpen size={14} className="shrink-0 text-brand-300" /> : <Folder size={14} className="shrink-0 text-slate-400" />}
            </>
          ) : (
            <FileText size={14} className="ml-[14px] shrink-0 text-slate-400" />
          )}
          <span className="truncate">{isRoot ? node.name : node.name}</span>
          {isMain && <span className="rounded bg-white/10 px-1.5 text-[10px] font-semibold text-slate-400">main</span>}
        </button>
        <div className="hidden shrink-0 items-center gap-0.5 group-hover:flex">
          {isFolder && canCreate && (
            <button title="Novo arquivo aqui" onClick={() => onNewInside(node.path)} className="rounded p-1 text-slate-400 hover:bg-white/10 hover:text-white">
              <FilePlus2 size={13} />
            </button>
          )}
          {!isRoot && canRename && (
            <button title="Renomear" onClick={() => onRename(node)} className="rounded p-1 text-slate-400 hover:bg-white/10 hover:text-white">
              <Pencil size={13} />
            </button>
          )}
          {!isRoot && canDelete && (
            <button title="Excluir" onClick={() => onDelete(node)} className="rounded p-1 text-slate-400 hover:bg-white/10 hover:text-red-400">
              <Trash2 size={13} />
            </button>
          )}
        </div>
      </div>
      {isFolder && isOpen && node.children?.map((child) => (
        <TreeItem
          key={child.path} node={child} depth={depth + 1} expanded={expanded} toggle={toggle}
          onOpen={onOpen} activePath={activePath} mainPath={mainPath}
          canWrite={canWrite} canDelete={canDelete} canRename={canRename} canCreate={canCreate}
          onNewInside={onNewInside} onRename={onRename} onDelete={onDelete}
        />
      ))}
    </div>
  );
}

// ── main modal ──
export function JobCodeWorkspaceModal({
  jobId, open, onClose,
}: {
  jobId: number; open: boolean; onClose: () => void;
}) {
  const { can } = useAuth();
  const canWrite = can(PERM.write);
  const canCreate = can(PERM.create);
  const canDelete = can(PERM.delete);
  const canRename = can(PERM.rename);

  const [tree, setTree] = useState<WorkspaceTree | null>(null);
  const [treeError, setTreeError] = useState<string | null>(null);
  const [loadingTree, setLoadingTree] = useState(false);
  const [expanded, setExpanded] = useState<Set<string>>(new Set([""]));

  const [files, setFiles] = useState<OpenFile[]>([]);
  const [activePath, setActivePath] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<{ kind: "ok" | "err"; msg: string } | null>(null);

  // dialog state
  const [dialog, setDialog] = useState<
    | { kind: "new-file"; base: string }
    | { kind: "new-folder"; base: string }
    | { kind: "rename"; node: TreeNode }
    | { kind: "delete"; node: TreeNode }
    | null
  >(null);

  const active = files.find((f) => f.path === activePath) ?? null;
  const dirty = active != null && active.value !== active.base;
  const anyDirty = files.some((f) => f.value !== f.base);
  const hasCredential = useMemo(
    () => !!active && dirty && CREDENTIAL_RE.test(active.value),
    [active, dirty]
  );

  const patch = useCallback((path: string, upd: Partial<OpenFile>) => {
    setFiles((prev) => prev.map((f) => (f.path === path ? { ...f, ...upd } : f)));
  }, []);

  const loadTree = useCallback(async () => {
    setLoadingTree(true);
    setTreeError(null);
    try {
      const data = await api.get<WorkspaceTree>(`/api/v1/jobs/${jobId}/workspace/tree`);
      setTree(data);
    } catch (err) {
      setTreeError(err instanceof Error ? err.message : "Falha ao carregar o workspace.");
    } finally {
      setLoadingTree(false);
    }
  }, [jobId]);

  // Load tree when opened; reset state when closed.
  useEffect(() => {
    if (!open) return;
    void loadTree();
  }, [open, loadTree]);

  useEffect(() => {
    if (open) return;
    setFiles([]);
    setActivePath(null);
    setDialog(null);
    setToast(null);
  }, [open]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 3500);
    return () => clearTimeout(t);
  }, [toast]);

  // Open main file automatically on first tree load.
  useEffect(() => {
    if (tree?.main_path && files.length === 0) {
      void openFile(tree.main_path);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tree]);

  const openFile = useCallback(
    async (path: string) => {
      setActivePath(path);
      if (files.some((f) => f.path === path)) return;
      const placeholder: OpenFile = {
        path, fileName: path.split("/").pop() ?? path, language: "text",
        base: "", value: "", mtime: null, readOnly: !canWrite, loading: true, conflict: false,
      };
      setFiles((prev) => [...prev, placeholder]);
      try {
        const data = await api.get<WorkspaceFile>(
          `/api/v1/jobs/${jobId}/workspace/file?path=${encodeURIComponent(path)}`
        );
        setFiles((prev) =>
          prev.map((f) =>
            f.path === path
              ? {
                  ...f, fileName: data.file_name, language: data.language, base: data.content,
                  value: data.content, mtime: data.last_modified_at, readOnly: !data.editable, loading: false,
                }
              : f
          )
        );
      } catch (err) {
        setFiles((prev) => prev.filter((f) => f.path !== path));
        setToast({ kind: "err", msg: err instanceof Error ? err.message : "Falha ao abrir arquivo." });
      }
    },
    [files, jobId, canWrite]
  );

  const closeTab = useCallback(
    (path: string) => {
      const f = files.find((x) => x.path === path);
      if (f && f.value !== f.base && !window.confirm(`Descartar alterações não salvas em ${f.fileName}?`)) return;
      setFiles((prev) => {
        const next = prev.filter((x) => x.path !== path);
        if (activePath === path) setActivePath(next.length ? next[next.length - 1].path : null);
        return next;
      });
    },
    [files, activePath]
  );

  const save = useCallback(async () => {
    if (!active || active.readOnly || active.value === active.base) return;
    if (CREDENTIAL_RE.test(active.value)) {
      const ok = window.confirm(
        "Detectamos um possível padrão de credencial no código (ex.: password=, secret=, token=).\n\n" +
          "Não salve senhas/tokens no código — use conexões cadastradas ou variáveis seguras.\n\nDeseja salvar mesmo assim?"
      );
      if (!ok) return;
    }
    setSaving(true);
    patch(active.path, { conflict: false });
    try {
      const saved = await api.put<WorkspaceFile>(`/api/v1/jobs/${jobId}/workspace/file`, {
        path: active.path,
        content: active.value,
        expected_last_modified_at: active.mtime,
      });
      patch(active.path, { base: saved.content, value: saved.content, mtime: saved.last_modified_at });
      setToast({ kind: "ok", msg: `${active.fileName} salvo.` });
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        patch(active.path, { conflict: true });
      } else {
        setToast({ kind: "err", msg: err instanceof Error ? err.message : "Falha ao salvar." });
      }
    } finally {
      setSaving(false);
    }
  }, [active, jobId, patch]);

  const reloadActive = useCallback(async () => {
    if (!active) return;
    if (active.value !== active.base && !window.confirm("Descartar alterações e recarregar?")) return;
    try {
      const data = await api.get<WorkspaceFile>(
        `/api/v1/jobs/${jobId}/workspace/file?path=${encodeURIComponent(active.path)}`
      );
      patch(active.path, {
        base: data.content, value: data.content, mtime: data.last_modified_at, conflict: false,
      });
    } catch {
      /* ignore */
    }
  }, [active, jobId, patch]);

  // Ctrl/Cmd+S saves the active tab.
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        void save();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, save]);

  // Warn on browser close with unsaved changes.
  useEffect(() => {
    if (!open || !anyDirty) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [open, anyDirty]);

  // ── dialog handlers ──
  async function submitDialog(input: string) {
    const d = dialog;
    if (!d) return;
    try {
      if (d.kind === "new-file") {
        const path = d.base ? `${d.base}/${input}` : input;
        await api.post(`/api/v1/jobs/${jobId}/workspace/file`, { path, content: "" });
        setDialog(null);
        await loadTree();
        setExpanded((prev) => new Set(prev).add(d.base));
        await openFile(path);
        setToast({ kind: "ok", msg: "Arquivo criado." });
      } else if (d.kind === "new-folder") {
        const path = d.base ? `${d.base}/${input}` : input;
        await api.post(`/api/v1/jobs/${jobId}/workspace/folder`, { path });
        setDialog(null);
        await loadTree();
        setExpanded((prev) => new Set(prev).add(path));
        setToast({ kind: "ok", msg: "Pasta criada." });
      } else if (d.kind === "rename") {
        const parent = d.node.path.includes("/") ? d.node.path.slice(0, d.node.path.lastIndexOf("/")) : "";
        const newPath = parent ? `${parent}/${input}` : input;
        await api.put(`/api/v1/jobs/${jobId}/workspace/rename`, { old_path: d.node.path, new_path: newPath });
        setDialog(null);
        // update any open tab that matched the old path
        setFiles((prev) =>
          prev.map((f) =>
            f.path === d.node.path ? { ...f, path: newPath, fileName: input } : f
          )
        );
        setActivePath((p) => (p === d.node.path ? newPath : p));
        await loadTree();
        setToast({ kind: "ok", msg: "Renomeado." });
      }
    } catch (err) {
      setToast({ kind: "err", msg: err instanceof Error ? err.message : "Operação falhou." });
    }
  }

  async function confirmDelete() {
    const d = dialog;
    if (!d || d.kind !== "delete") return;
    try {
      const isFolder = d.node.type === "folder";
      const url = isFolder
        ? `/api/v1/jobs/${jobId}/workspace/folder?path=${encodeURIComponent(d.node.path)}`
        : `/api/v1/jobs/${jobId}/workspace/file?path=${encodeURIComponent(d.node.path)}`;
      await api.del(url);
      setDialog(null);
      setFiles((prev) => prev.filter((f) => f.path !== d.node.path && !f.path.startsWith(`${d.node.path}/`)));
      setActivePath((p) => (p === d.node.path ? null : p));
      await loadTree();
      setToast({ kind: "ok", msg: isFolder ? "Pasta excluída." : "Arquivo excluído." });
    } catch (err) {
      setToast({ kind: "err", msg: err instanceof Error ? err.message : "Falha ao excluir." });
    }
  }

  if (!open) return null;

  const monacoLang = active ? (MONACO_LANGUAGE[active.language] ?? "plaintext") : "plaintext";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6">
      <div className="fixed inset-0 bg-graphite-950/60 backdrop-blur-sm" onClick={anyDirty ? undefined : onClose} />
      <div className="relative z-10 flex h-[90vh] w-[95vw] max-w-[1500px] flex-col overflow-hidden rounded-2xl border border-graphite-800 bg-graphite-950 shadow-card-hover">
        {/* header */}
        <div className="flex items-center justify-between border-b border-white/10 px-4 py-2.5">
          <div className="flex min-w-0 items-center gap-2">
            <Code2Icon />
            <span className="text-sm font-semibold text-slate-100">Workspace de código</span>
            {tree && <span className="truncate font-mono text-xs text-slate-500">{tree.workspace_path}</span>}
            {!canWrite && (
              <span className="inline-flex items-center gap-1 rounded-full bg-white/10 px-2 py-0.5 text-[11px] font-medium text-slate-400">
                <Lock size={11} /> somente leitura
              </span>
            )}
          </div>
          <button onClick={onClose} className="rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-white/10 hover:text-white">
            <X size={18} />
          </button>
        </div>

        <div className="flex min-h-0 flex-1">
          {/* explorer */}
          <aside className="flex w-64 shrink-0 flex-col border-r border-white/10 bg-graphite-900/50">
            <div className="flex items-center justify-between px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
              <span>Explorador</span>
              <div className="flex items-center gap-0.5">
                {canCreate && (
                  <>
                    <button title="Novo arquivo" onClick={() => setDialog({ kind: "new-file", base: "" })} className="rounded p-1 text-slate-400 hover:bg-white/10 hover:text-white">
                      <FilePlus2 size={14} />
                    </button>
                    <button title="Nova pasta" onClick={() => setDialog({ kind: "new-folder", base: "" })} className="rounded p-1 text-slate-400 hover:bg-white/10 hover:text-white">
                      <FolderPlus size={14} />
                    </button>
                  </>
                )}
                <button title="Recarregar" onClick={() => void loadTree()} className="rounded p-1 text-slate-400 hover:bg-white/10 hover:text-white">
                  <RefreshCw size={14} className={loadingTree ? "animate-spin" : ""} />
                </button>
              </div>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto pb-3">
              {treeError ? (
                <div className="flex items-center gap-2 px-3 py-4 text-xs text-red-300">
                  <AlertTriangle size={14} /> {treeError}
                </div>
              ) : tree ? (
                <TreeItem
                  node={tree.tree} depth={0} expanded={expanded}
                  toggle={(p) => setExpanded((prev) => {
                    const next = new Set(prev);
                    next.has(p) ? next.delete(p) : next.add(p);
                    return next;
                  })}
                  onOpen={(n) => void openFile(n.path)}
                  activePath={activePath} mainPath={tree.main_path}
                  canWrite={canWrite} canDelete={canDelete} canRename={canRename} canCreate={canCreate}
                  onNewInside={(folder) => { setExpanded((prev) => new Set(prev).add(folder)); setDialog({ kind: "new-file", base: folder }); }}
                  onRename={(n) => setDialog({ kind: "rename", node: n })}
                  onDelete={(n) => setDialog({ kind: "delete", node: n })}
                />
              ) : (
                <div className="px-3 py-4 text-xs text-slate-500">Carregando…</div>
              )}
            </div>
          </aside>

          {/* editor area */}
          <section className="flex min-w-0 flex-1 flex-col">
            {/* tabs */}
            <div className="flex items-stretch gap-px overflow-x-auto border-b border-white/10 bg-graphite-900/30">
              {files.length === 0 && (
                <div className="px-4 py-2.5 text-xs text-slate-500">Nenhum arquivo aberto</div>
              )}
              {files.map((f) => {
                const fdirty = f.value !== f.base;
                return (
                  <div
                    key={f.path}
                    className={cn(
                      "group flex shrink-0 items-center gap-2 border-r border-white/5 px-3 py-2 text-xs",
                      f.path === activePath ? "bg-graphite-950 text-slate-100" : "text-slate-400 hover:bg-white/5"
                    )}
                  >
                    <button onClick={() => setActivePath(f.path)} className="flex items-center gap-1.5">
                      <FileText size={13} className="shrink-0" />
                      <span className="max-w-[160px] truncate">{f.fileName}</span>
                    </button>
                    {fdirty && <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-brand-400" title="não salvo" />}
                    <button onClick={() => closeTab(f.path)} className="rounded p-0.5 text-slate-500 opacity-0 hover:bg-white/10 hover:text-white group-hover:opacity-100">
                      <X size={12} />
                    </button>
                  </div>
                );
              })}
            </div>

            {/* toolbar */}
            {active && (
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/10 px-4 py-2">
                <div className="flex min-w-0 items-center gap-2 text-xs text-slate-400">
                  <span className="truncate font-mono">{active.path}</span>
                  <span className="rounded-full bg-white/10 px-2 py-0.5 font-semibold text-slate-300">
                    {LANG_LABEL[active.language] ?? active.language}
                  </span>
                  {active.readOnly && (
                    <span className="inline-flex items-center gap-1 text-slate-500"><Lock size={11} /> leitura</span>
                  )}
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <button onClick={() => void reloadActive()} className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium text-slate-300 hover:bg-white/10 hover:text-white">
                    <RefreshCw size={13} /> Recarregar
                  </button>
                  {!active.readOnly && (
                    <button
                      onClick={() => void save()}
                      disabled={!dirty || saving}
                      className={cn(
                        "inline-flex items-center gap-1.5 rounded-md px-3 py-1 text-xs font-semibold transition-colors",
                        dirty ? "bg-brand-500 text-white hover:bg-brand-600" : "cursor-not-allowed bg-white/10 text-slate-500"
                      )}
                    >
                      <Save size={13} /> {saving ? "Salvando…" : "Salvar"}
                    </button>
                  )}
                </div>
              </div>
            )}

            {/* alerts */}
            {active?.conflict && (
              <div className="flex items-start gap-2 border-b border-red-500/20 bg-red-500/10 px-4 py-2 text-xs text-red-200">
                <AlertTriangle size={14} className="mt-0.5 shrink-0" />
                Este arquivo foi alterado por outro usuário ou processo. Recarregue antes de salvar.
              </div>
            )}
            {hasCredential && (
              <div className="flex items-start gap-2 border-b border-amber-500/20 bg-amber-500/10 px-4 py-2 text-xs text-amber-200">
                <ShieldAlert size={14} className="mt-0.5 shrink-0" />
                Possível credencial detectada. Não salve senhas/tokens aqui — use conexões cadastradas ou variáveis seguras.
              </div>
            )}
            {toast && (
              <div className={cn(
                "flex items-center gap-2 border-b px-4 py-2 text-xs",
                toast.kind === "ok" ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-200" : "border-red-500/20 bg-red-500/10 text-red-200"
              )}>
                {toast.kind === "ok" ? <Check size={14} /> : <AlertTriangle size={14} />} {toast.msg}
              </div>
            )}

            {/* editor */}
            <div className="min-h-0 flex-1">
              {active ? (
                active.loading ? (
                  <div className="p-6 text-sm text-slate-400">Carregando arquivo…</div>
                ) : (
                  <Editor
                    key={active.path}
                    height="100%"
                    theme="vs-dark"
                    language={monacoLang}
                    value={active.value}
                    onChange={(v) => patch(active.path, { value: v ?? "" })}
                    options={{
                      readOnly: active.readOnly,
                      fontSize: 13,
                      fontFamily: "JetBrains Mono, ui-monospace, monospace",
                      minimap: { enabled: true },
                      scrollBeyondLastLine: false,
                      automaticLayout: true,
                      tabSize: 4,
                    }}
                    loading={<div className="p-6 text-sm text-slate-400">Carregando editor…</div>}
                  />
                )
              ) : (
                <div className="flex h-full items-center justify-center text-sm text-slate-500">
                  Selecione um arquivo no explorador para começar.
                </div>
              )}
            </div>

            {/* status bar */}
            <div className="flex items-center justify-between border-t border-white/10 bg-brand-600/90 px-4 py-1 text-[11px] text-white">
              <div className="flex items-center gap-3">
                <span>Job #{jobId}</span>
                {active && <span>{active.fileName}{dirty ? " •" : ""}</span>}
              </div>
              <div className="flex items-center gap-3">
                {active?.mtime && <span>modificado {new Date(active.mtime).toLocaleString("pt-BR")}</span>}
                {active && <span>{fmtBytes(new TextEncoder().encode(active.value).length)}</span>}
              </div>
            </div>
          </section>
        </div>

        {/* dialogs */}
        {dialog?.kind === "new-file" && (
          <InputDialog
            title={dialog.base ? `Novo arquivo em ${dialog.base}/` : "Novo arquivo"}
            label="Nome do arquivo (extensões: .py .sql .sh .json .yaml .yml .md .txt)"
            initial="" confirmLabel="Criar"
            onSubmit={submitDialog} onCancel={() => setDialog(null)}
          />
        )}
        {dialog?.kind === "new-folder" && (
          <InputDialog
            title={dialog.base ? `Nova pasta em ${dialog.base}/` : "Nova pasta"}
            label="Nome da pasta" initial="" confirmLabel="Criar"
            onSubmit={submitDialog} onCancel={() => setDialog(null)}
          />
        )}
        {dialog?.kind === "rename" && (
          <InputDialog
            title="Renomear" label="Novo nome"
            initial={dialog.node.name} confirmLabel="Renomear"
            onSubmit={submitDialog} onCancel={() => setDialog(null)}
          />
        )}
        {dialog?.kind === "delete" && (
          <ConfirmDialog
            title={dialog.node.type === "folder" ? "Excluir pasta" : "Excluir arquivo"}
            message={
              dialog.node.type === "folder"
                ? `A pasta "${dialog.node.name}" será excluída (precisa estar vazia). Esta ação faz backup, mas não pode ser desfeita pela interface.`
                : `O arquivo "${dialog.node.name}" será excluído. Um backup é gerado automaticamente.`
            }
            confirmLabel="Excluir" danger
            onConfirm={confirmDelete} onCancel={() => setDialog(null)}
          />
        )}
      </div>
    </div>
  );
}

// tiny inline icon to avoid another import name clash
function Code2Icon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-brand-400">
      <path d="m18 16 4-4-4-4M6 8l-4 4 4 4M14.5 4l-5 16" />
    </svg>
  );
}
