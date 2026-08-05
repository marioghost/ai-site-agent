import { Navigate, useLocation } from "react-router-dom";

export default function KnowledgeProfilePage() {
  const location = useLocation();
  return (
    <Navigate
      to={{ pathname: "/knowledge/site", search: location.search, hash: location.hash }}
      replace
    />
  );
}
