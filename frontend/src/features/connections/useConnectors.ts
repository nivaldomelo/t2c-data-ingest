import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { ConnectorMeta } from "@/features/connections/types";

/** Carrega o registry de conectores (metadados que dirigem o formulário dinâmico). */
export function useConnectors() {
  return useQuery({
    queryKey: ["connection-types"],
    queryFn: () => api.get<ConnectorMeta[]>("/api/v1/connections/types"),
    staleTime: 5 * 60 * 1000,
  });
}
