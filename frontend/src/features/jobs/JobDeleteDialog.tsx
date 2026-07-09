import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, Archive } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { Modal, SecondaryButton } from "@/components/ui";

interface DeleteResult {
  success: boolean;
  message: string;
  job_id: number;
  archived_code_path: string | null;
}

export function JobDeleteDialog({
  job, open, onClose, onDeleted,
}: {
  job: { id: number; name: string }; open: boolean; onClose: () => void; onDeleted: () => void;
}) {
  const [reason, setReason] = useState("");
  const [blocked, setBlocked] = useState<string | null>(null);

  const del = useMutation({
    mutationFn: () => api.del<DeleteResult>(`/api/v1/jobs/${job.id}`, { reason: reason.trim() || null }),
    onMutate: () => setBlocked(null),
    onSuccess: () => onDeleted(),
    onError: (err) => {
      // 409 = dependency block; show the backend's explanatory message inline.
      setBlocked(err instanceof ApiError ? err.message : "Não foi possível excluir o job.");
    },
  });

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Excluir job"
      width="max-w-lg"
      footer={
        <>
          <SecondaryButton onClick={onClose}>Cancelar</SecondaryButton>
          <button
            onClick={() => del.mutate()}
            disabled={del.isPending}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-red-500 px-4 text-sm font-semibold text-white transition-colors hover:bg-red-600 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {del.isPending ? "Excluindo…" : "Excluir job"}
          </button>
        </>
      }
    >
      <p className="text-sm text-gray-700">
        Tem certeza que deseja excluir <span className="font-semibold">{job.name}</span>?
      </p>
      <div className="mt-3 flex items-start gap-2 rounded-lg border border-gray-200 bg-gray-50 px-3.5 py-2.5 text-sm text-gray-600">
        <Archive size={16} className="mt-0.5 shrink-0 text-brand-500" />
        O job será removido da listagem ativa e o código associado será <b>movido para a pasta de
        arquivo</b> do projeto. Essa ação não apagará definitivamente os arquivos do job.
      </div>

      <label className="mt-4 mb-1 block text-xs font-medium text-gray-600">Motivo (opcional)</label>
      <input
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800 outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20"
        placeholder="ex.: job substituído pelo pipeline X"
      />

      {blocked && (
        <div className="mt-4 flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3.5 py-2.5 text-sm text-amber-800">
          <AlertTriangle size={16} className="mt-0.5 shrink-0" /> {blocked}
        </div>
      )}
    </Modal>
  );
}
