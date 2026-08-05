import { Navigate, useLocation } from "react-router-dom";

export default function SourcesPage() {
  const location = useLocation();
  return (
    <Navigate
      to={{ pathname: "/knowledge/library", search: location.search, hash: location.hash }}
      replace
    />
  );
}
