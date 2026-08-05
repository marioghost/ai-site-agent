import { Navigate, useLocation } from "react-router-dom";

export default function IndexingPage() {
  const location = useLocation();
  return (
    <Navigate
      to={{ pathname: "/knowledge/update", search: location.search, hash: location.hash }}
      replace
    />
  );
}
