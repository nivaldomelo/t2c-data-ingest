import { Navigate, Route, Routes } from "react-router-dom";

import AppLayout from "@/components/layout/AppLayout";
import { useAuth } from "@/lib/auth";
import LoginPage from "@/features/auth/LoginPage";
import DashboardPage from "@/features/dashboard/DashboardPage";
import ClustersPage from "@/features/clusters/ClustersPage";
import JobsPage from "@/features/jobs/JobsPage";
import PipelinesPage from "@/features/pipelines/PipelinesPage";
import ExecutionsPage from "@/features/executions/ExecutionsPage";
import AirflowPage from "@/features/airflow/AirflowPage";

export default function App() {
  const { me, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-400">
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
      <Route element={<AppLayout />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/clusters" element={<ClustersPage />} />
        <Route path="/jobs" element={<JobsPage />} />
        <Route path="/pipelines" element={<PipelinesPage />} />
        <Route path="/executions" element={<ExecutionsPage />} />
        <Route path="/airflow" element={<AirflowPage />} />
      </Route>
      <Route path="/login" element={<Navigate to="/" replace />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
