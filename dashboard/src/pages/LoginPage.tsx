import { FormEvent, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useTranslation } from "../i18n";
import LanguageSwitcher from "../components/LanguageSwitcher";

export default function LoginPage() {
  const { t } = useTranslation();
  const { login, user, loading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  // S007 (G6-P3) — Home is the product default; Overview retired.
  const from = (location.state as { from?: string } | null)?.from ?? "/home";

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (!loading && user) {
    return <Navigate to={from} replace />;
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(username.trim(), password);
      navigate(from, { replace: true });
    } catch {
      setError(t("auth.error_invalid"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="login-page">
      <div className="login-page__top">
        <LanguageSwitcher />
      </div>
      <div className="login-card">
        <h1 className="login-card__title">{t("auth.sign_in")}</h1>
        <p className="login-card__subtitle">{t("app.header")}</p>
        <form className="login-form" onSubmit={onSubmit}>
          <label className="login-field">
            <span>{t("auth.username")}</span>
            <input
              type="text"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </label>
          <label className="login-field">
            <span>{t("auth.password")}</span>
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
          {error ? <p className="login-form__error">{error}</p> : null}
          <button type="submit" className="login-form__submit" disabled={submitting}>
            {submitting ? t("auth.signing_in") : t("auth.log_in")}
          </button>
        </form>
      </div>
    </div>
  );
}
