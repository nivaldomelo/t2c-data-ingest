import { useQuery } from "@tanstack/react-query";
import { FileWarning, Lock } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { CodeViewer, EmptyState } from "@/components/ui";
import { Skeleton } from "@/components/ui/LoadingSkeleton";
import type { JobCode } from "@/features/jobs/types";

export function JobCodeTab({ jobId }: { jobId: number }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["job-code", jobId],
    queryFn: () => api.get<JobCode>(`/api/v1/jobs/${jobId}/code`),
    retry: false,
  });

  if (isLoading) {
    return <Skeleton className="h-80 rounded-2xl" />;
  }

  if (error) {
    const status = error instanceof ApiError ? error.status : 0;
    const message = error instanceof Error ? error.message : "Não foi possível carregar o código.";
    if (status === 403) {
      return (
        <EmptyState
          icon={<Lock size={24} />}
          title="Sem acesso ao código"
          description={message}
        />
      );
    }
    return (
      <EmptyState
        icon={<FileWarning size={24} />}
        title="Código indisponível"
        description={message}
      />
    );
  }

  if (!data) return null;

  return <CodeViewer content={data.content} language={data.language} path={data.script_path} readOnly={data.read_only} />;
}
