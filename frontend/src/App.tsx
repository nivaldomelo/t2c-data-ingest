import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "@/components/layout/AppShell";
import { useAuth } from "@/lib/auth";
import LoginPage from "@/features/auth/LoginPage";
import DashboardPage from "@/features/dashboard/DashboardPage";
import ClustersPage from "@/features/clusters/ClustersPage";
import LibrariesPage from "@/features/libraries/LibrariesPage";
import RuntimePage from "@/features/runtime/RuntimePage";
import ConnectionsPage from "@/features/connections/ConnectionsPage";
import IngestionControlPage from "@/features/ingestion-control/IngestionControlPage";
import VariablesPage from "@/features/variables/VariablesPage";
import JobsPage from "@/features/jobs/JobsPage";
import JobDetailPage from "@/features/jobs/JobDetailPage";
import PipelinesPage from "@/features/pipelines/PipelinesPage";
import PipelineDetailPage from "@/features/pipelines/PipelineDetailPage";
import SchedulesPage from "@/features/schedules/SchedulesPage";
import TagsPage from "@/features/tags/TagsPage";
import ExecutionsPage from "@/features/executions/ExecutionsPage";
import ExecutionDetailPage from "@/features/executions/ExecutionDetailPage";
import BackfillsPage from "@/features/backfill/BackfillsPage";
import AlertsPage from "@/features/alerts/AlertsPage";
import AuditPage from "@/features/audit/AuditPage";
import AirflowPage from "@/features/airflow/AirflowPage";

export default function App() {
  const { me, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-50 text-gray-400">
        Carregando…
      </div>
    );
  }

  if (!me) {
    return (
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }

  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/connections" element={<ConnectionsPage />} />
        <Route path="/ingestion-control" element={<IngestionControlPage />} />
        <Route path="/variables" element={<VariablesPage />} />
        <Route path="/clusters" element={<ClustersPage />} />
        <Route path="/libraries" element={<LibrariesPage />} />
        <Route path="/runtime" element={<RuntimePage />} />
        <Route path="/jobs" element={<JobsPage />} />
        <Route path="/jobs/:id" element={<JobDetailPage />} />
        <Route path="/pipelines" element={<PipelinesPage />} />
        <Route path="/pipelines/:id" element={<PipelineDetailPage />} />
        <Route path="/schedules" element={<SchedulesPage />} />
        <Route path="/tags" element={<TagsPage />} />
        <Route path="/executions" element={<ExecutionsPage />} />
        <Route path="/executions/:id" element={<ExecutionDetailPage />} />
        <Route path="/backfills" element={<BackfillsPage />} />
        <Route path="/alerts" element={<AlertsPage />} />
        <Route path="/audit" element={<AuditPage />} />
        <Route path="/airflow" element={<AirflowPage />} />
      </Route>
      <Route path="/login" element={<Navigate to="/" replace />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
