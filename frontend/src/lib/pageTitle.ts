export const APP_TITLE = "T2C Data Ingest";

// Route prefix -> page label. Longest matching prefix wins. "/" (dashboard) keeps the base title.
const TITLES: [string, string][] = [
  ["/jobs", "Jobs"],
  ["/pipelines", "Pipelines"],
  ["/executions", "Execuções"],
  ["/analytics", "Análise de Ingestões"],
  ["/schedules", "Schedules"],
  ["/connections", "Origens"],
  ["/variables", "Variáveis"],
  ["/ingestion-control", "Controle de Ingestão"],
  ["/clusters", "Clusters"],
  ["/runtime", "Ambiente de Execução"],
  ["/libraries", "Bibliotecas"],
  ["/alerts", "Alertas"],
  ["/data-quality", "Data Quality"],
  ["/backfills", "Reprocessamentos"],
  ["/audit", "Auditoria"],
  ["/access", "Usuários"],
  ["/tags", "Tags"],
  ["/airflow", "Airflow legado"],
];

/** Document title for a path: "T2C Data Ingest" on the dashboard, "T2C Data Ingest | <page>" elsewhere. */
export function titleForPath(pathname: string): string {
  const match = TITLES
    .filter(([prefix]) => pathname === prefix || pathname.startsWith(prefix + "/"))
    .sort((a, b) => b[0].length - a[0].length)[0];
  return match ? `${APP_TITLE} | ${match[1]}` : APP_TITLE;
}
