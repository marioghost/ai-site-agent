import { Navigate, useLocation } from "react-router-dom";

/**
 * S005 (G3-P1) — Ask (`/ask`) is the canonical product owner for J5.
 * Legacy `/chat` bookmarks keep working via this compatibility redirect.
 */
export default function ChatTestPage() {
  const location = useLocation();
  return (
    <Navigate
      to={{ pathname: "/ask", search: location.search, hash: location.hash }}
      replace
    />
  );
}
