import { lazy, Suspense, type ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import RequireAuth from "./components/auth/RequireAuth";
import RequireEngineeringMode from "./components/auth/RequireEngineeringMode";
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
const KnowledgeProfilePage = lazy(() => import("./pages/KnowledgeProfilePage"));
const UsersPage = lazy(() => import("./pages/UsersPage"));
const EpistemicHealthPage = lazy(() => import("./pages/EpistemicHealthPage"));

const HomeScreen = lazy(() => import("./features/home/HomeScreen"));
const LibraryScreen = lazy(() => import("./features/knowledge/library/LibraryScreen"));
const UpdateScreen = lazy(() => import("./features/knowledge/update/UpdateScreen"));
const SiteScreen = lazy(() => import("./features/knowledge/site/SiteScreen"));
const AskScreen = lazy(() => import("./features/ask/AskScreen"));
const PerformanceScreen = lazy(
  () => import("./features/insights/performance/PerformanceScreen")
);
const ActivityScreen = lazy(() => import("./features/insights/activity/ActivityScreen"));
const GeneralScreen = lazy(() => import("./features/settings/general/GeneralScreen"));
const ModelsScreen = lazy(() => import("./features/settings/models/ModelsScreen"));
const AnswersScreen = lazy(() => import("./features/settings/answers/AnswersScreen"));
const AccessScreen = lazy(() => import("./features/settings/access/AccessScreen"));
const EngStatusScreen = lazy(() => import("./features/engineering/status/EngStatusScreen"));
const EngAskDetailsScreen = lazy(
  () => import("./features/engineering/ask-details/EngAskDetailsScreen")
);
const EngKnowledgeScreen = lazy(
  () => import("./features/engineering/knowledge/EngKnowledgeScreen")
);
const EngTensionsScreen = lazy(
  () => import("./features/engineering/tensions/EngTensionsScreen")
);
const EngAdvancedScreen = lazy(
  () => import("./features/engineering/advanced/EngAdvancedScreen")
);
const EngBuildScreen = lazy(() => import("./features/engineering/build/EngBuildScreen"));

const KnowledgeLayout = lazy(() => import("./layouts/KnowledgeLayout"));
const InsightsLayout = lazy(() => import("./layouts/InsightsLayout"));
const SettingsLayout = lazy(() => import("./layouts/SettingsLayout"));
const EngineeringLayout = lazy(() => import("./layouts/EngineeringLayout"));

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
              path="/knowledge-profile"
              element={
                <LazyPage>
                  <KnowledgeProfilePage />
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

          {/* Canonical product routes (S001 substrate / scaffolds) */}
          <Route
            path="/home"
            element={
              <LazyPage>
                <HomeScreen />
              </LazyPage>
            }
          />
          <Route
            path="/ask"
            element={
              <LazyPage>
                <AskScreen />
              </LazyPage>
            }
          />
          <Route
            path="/knowledge"
            element={
              <LazyPage>
                <KnowledgeLayout />
              </LazyPage>
            }
          >
            <Route index element={<Navigate to="library" replace />} />
            <Route path="library" element={<LibraryScreen />} />
            <Route path="update" element={<UpdateScreen />} />
            <Route path="site" element={<SiteScreen />} />
          </Route>
          <Route
            path="/insights"
            element={
              <LazyPage>
                <InsightsLayout />
              </LazyPage>
            }
          >
            <Route index element={<Navigate to="performance" replace />} />
            <Route path="performance" element={<PerformanceScreen />} />
            <Route path="activity" element={<ActivityScreen />} />
          </Route>

          <Route element={<RequireAuth roles={["admin"]} />}>
            {/* Q2 — /settings → /settings/general (single Settings home) */}
            <Route
              path="/settings"
              element={
                <LazyPage>
                  <SettingsLayout />
                </LazyPage>
              }
            >
              <Route index element={<Navigate to="general" replace />} />
              <Route path="general" element={<GeneralScreen />} />
              <Route path="models" element={<ModelsScreen />} />
              <Route path="answers" element={<AnswersScreen />} />
              <Route path="access" element={<AccessScreen />} />
            </Route>

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

            {/* Engineering Mode routes */}
            <Route element={<RequireEngineeringMode />}>
              <Route
                path="/engineering"
                element={
                  <LazyPage>
                    <EngineeringLayout />
                  </LazyPage>
                }
              >
                <Route index element={<Navigate to="status" replace />} />
                <Route path="status" element={<EngStatusScreen />} />
                <Route path="ask-details" element={<EngAskDetailsScreen />} />
                <Route path="knowledge" element={<EngKnowledgeScreen />} />
                <Route path="tensions" element={<EngTensionsScreen />} />
                <Route path="advanced" element={<EngAdvancedScreen />} />
                <Route path="build" element={<EngBuildScreen />} />
              </Route>
            </Route>
          </Route>
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/overview" replace />} />
    </Routes>
  );
}
