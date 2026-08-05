import { Navigate, useLocation } from "react-router-dom";

export default function UsersPage() {
  const location = useLocation();
  return (
    <Navigate
      to={{ pathname: "/settings/access", search: location.search, hash: location.hash }}
      replace
    />
  );
}
