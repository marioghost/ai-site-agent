import { Navigate, useLocation } from "react-router-dom";

/**
 * S007 (G6-P3) — Overview is retired as the product home; `/home` is the
 * canonical product default (S005/HomeScreen). This page now exists only as
 * a redirect-compatibility shim so old `/overview` bookmarks/links keep
 * working, preserving any query string or hash.
 *
 * G6-P2 widget redistribution: every capability Overview used to host has an
 * owner elsewhere —
 *   - analytics preview           -> `/insights/performance` (PerformanceScreen, full analytics)
 *   - knowledge base readiness    -> `/knowledge/library` (SourcesSummaryCards/SourcesKnowledgeMiniCard) and `/home` (readiness links)
 *   - subsystem/backend health    -> `/engineering/status` (EngStatusScreen, same SubsystemHealthPanel)
 *   - LLM runtime/benchmark panel -> `/engineering/status` (EngStatusScreen)
 *   - Knowledge OS release tags   -> `/engineering/status` (EngStatusScreen)
 *   - epistemic tension summary   -> `/engineering/tensions` (EngTensionsScreen) and `/diagnostics/epistemic-health`
 */
export default function OverviewPage() {
  const location = useLocation();
  return (
    <Navigate
      to={{ pathname: "/home", search: location.search, hash: location.hash }}
      replace
    />
  );
}
