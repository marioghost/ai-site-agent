import { Navigate, useLocation } from "react-router-dom";

export default function LogsPage() {
  const location = useLocation();
  return (
    <Navigate
      to={{ pathname: "/insights/activity", search: location.search, hash: location.hash }}
      replace
    />
  );
}
