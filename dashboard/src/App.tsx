import { lazy, Suspense, type ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import RequireAuth from "./components/auth/RequireAuth";
import DashboardLayout from "./components/layout/DashboardLayout";
import { useTranslation } from "./i18n";
import { LoadingState } from "./ui";

const LoginPage = lazy(() => import("./pages/LoginPage"));
const OverviewPage = lazy(() => import("./pages/OverviewPage"));
const AnalyticsPage = lazy(() => import("./pages/AnalyticsPage"));
const LogsPage = lazy(() => import("./pages/LogsPage"));
const SourcesPage = lazy(() => import("./pages/SourcesPage"));
const IndexingPage = lazy(() => import("./pages/IndexingPage"));
const ChatTestPage = lazy(() => import("./pages/ChatTestPage"));
const SettingsPage = lazy(() => import("./pages/SettingsPage"));
const KnowledgeProfilePage = lazy(() => import("./pages/KnowledgeProfilePage"));
const UsersPage = lazy(() => import("./pages/UsersPage"));
const EpistemicHealthPage = lazy(() => import("./pages/EpistemicHealthPage"));

function RouteFallback() {
  const { t } = useTranslation();
  return <LoadingState label={t("common.loading")} />;
}

function LazyPage({ children }: { children: ReactNode }) {
  return <Suspense fallback={<RouteFallback />}>{children}</Suspense>;
}

export default function App() {
  return (
    <Routes>
      <Route
        path="/login"
        element={
          <LazyPage>
            <LoginPage />
          </LazyPage>
        }
      />
      <Route element={<RequireAuth />}>
        <Route element={<DashboardLayout />}>
          <Route path="/" element={<Navigate to="/overview" replace />} />
          <Route
            path="/overview"
            element={
              <LazyPage>
                <OverviewPage />
              </LazyPage>
            }
          />
          <Route
            path="/analytics"
            element={
              <LazyPage>
                <AnalyticsPage />
              </LazyPage>
            }
          />
          <Route
            path="/logs"
            element={
              <LazyPage>
                <LogsPage />
              </LazyPage>
            }
          />
          <Route element={<RequireAuth roles={["admin", "operator"]} />}>
            <Route
              path="/sources"
              element={
                <LazyPage>
                  <SourcesPage />
                </LazyPage>
              }
            />
            <Route
              path="/indexing"
              element={
                <LazyPage>
                  <IndexingPage />
                </LazyPage>
              }
            />
            <Route
              path="/chat"
              element={
                <LazyPage>
                  <ChatTestPage />
                </LazyPage>
              }
            />
          </Route>
          <Route element={<RequireAuth roles={["admin"]} />}>
            <Route
              path="/settings"
              element={
                <LazyPage>
                  <SettingsPage />
                </LazyPage>
              }
            />
            <Route
              path="/knowledge-profile"
              element={
                <LazyPage>
                  <KnowledgeProfilePage />
                </LazyPage>
              }
            />
            <Route
              path="/diagnostics/epistemic-health"
              element={
                <LazyPage>
                  <EpistemicHealthPage />
                </LazyPage>
              }
            />
            <Route
              path="/understanding"
              element={<Navigate to="/diagnostics/epistemic-health" replace />}
            />
            <Route
              path="/users"
              element={
                <LazyPage>
                  <UsersPage />
                </LazyPage>
              }
            />
          </Route>
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/overview" replace />} />
    </Routes>
  );
}
