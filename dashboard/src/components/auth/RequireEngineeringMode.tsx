import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { useEngineeringMode } from "../../context/EngineeringModeContext";

/**
 * Q6 — Mode OFF → redirect /settings/general (never 403/blank/hidden scaffold).
 * Owner/admin only when Mode on (RFC-101 §2.1).
 */
export default function RequireEngineeringMode() {
  const { user, loading } = useAuth();
  const { enabled } = useEngineeringMode();
  const location = useLocation();

  if (loading) {
    return (
      <div className="auth-loading">
        <div className="auth-loading__spinner" aria-hidden />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  if (!enabled || user.role !== "admin") {
    return <Navigate to="/settings/general" replace />;
  }

  return <Outlet />;
}
