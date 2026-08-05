import { Navigate, useLocation } from "react-router-dom";

export default function AnalyticsPage() {
  const location = useLocation();
  return (
    <Navigate
      to={{ pathname: "/insights/performance", search: location.search, hash: location.hash }}
      replace
    />
  );
}
