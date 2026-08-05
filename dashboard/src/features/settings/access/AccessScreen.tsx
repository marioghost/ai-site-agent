import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  activateUser,
  changeUserPassword,
  createUser,
  deactivateUser,
  deleteUser,
  listUsers,
  updateUser,
} from "../../../api/client";
import { useAuth } from "../../../context/AuthContext";
import { useTranslation } from "../../../i18n";
import {
  Alert,
  Button,
  CheckboxField,
  DataTable,
  Field,
  FormStack,
  Input,
  LoadingState,
  Modal,
  PageHeader,
  PageLayout,
  Select,
  StatusBadge,
} from "../../../ui";
import type { Column } from "../../../ui";
import type { UserRecord, UserRole } from "../../../types";

type FormMode = "create" | "edit" | "password" | null;

const ROLES: UserRole[] = ["admin", "operator", "viewer"];

export default function AccessScreen() {
  const { t } = useTranslation();
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<UserRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<FormMode>(null);
  const [selected, setSelected] = useState<UserRecord | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [role, setRole] = useState<UserRole>("viewer");
  const [isActive, setIsActive] = useState(true);
  const [password, setPassword] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setUsers(await listUsers());
    } catch {
      setError(t("users.error_load"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  function openCreate() {
    setSelected(null);
    setUsername("");
    setEmail("");
    setDisplayName("");
    setRole("viewer");
    setIsActive(true);
    setPassword("");
    setFormError(null);
    setMode("create");
  }

  function openEdit(u: UserRecord) {
    setSelected(u);
    setUsername(u.username);
    setEmail(u.email ?? "");
    setDisplayName(u.display_name);
    setRole(u.role);
    setIsActive(u.is_active);
    setPassword("");
    setFormError(null);
    setMode("edit");
  }

  function openPassword(u: UserRecord) {
    setSelected(u);
    setPassword("");
    setFormError(null);
    setMode("password");
  }

  function closeModal() {
    setMode(null);
    setSelected(null);
    setFormError(null);
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setFormError(null);
    try {
      if (mode === "create") {
        await createUser({
          username: username.trim(),
          email: email.trim() || null,
          display_name: displayName.trim(),
          role,
          is_active: isActive,
          password,
        });
      } else if (mode === "edit" && selected) {
        await updateUser(selected.id, {
          username: username.trim(),
          email: email.trim() || null,
          display_name: displayName.trim(),
          role,
          is_active: isActive,
        });
      } else if (mode === "password" && selected) {
        await changeUserPassword(selected.id, password);
      }
      closeModal();
      await load();
    } catch {
      setFormError(t("users.error_save"));
    } finally {
      setSaving(false);
    }
  }

  async function toggleActive(u: UserRecord) {
    try {
      if (u.is_active) await deactivateUser(u.id);
      else await activateUser(u.id);
      await load();
    } catch {
      setError(t("users.error_save"));
    }
  }

  async function onDelete(u: UserRecord) {
    if (!window.confirm(t("users.confirm_delete"))) return;
    try {
      await deleteUser(u.id);
      await load();
    } catch {
      setError(t("users.error_save"));
    }
  }

  const roleLabel = useMemo(
    () => (r: UserRole) => t(`users.role.${r}` as "users.role.admin"),
    [t]
  );

  const columns: Column<UserRecord>[] = useMemo(
    () => [
      { id: "username", header: t("users.col.username"), cell: (u) => u.username },
      { id: "display_name", header: t("users.col.display_name"), cell: (u) => u.display_name },
      {
        id: "email",
        header: t("users.col.email"),
        cell: (u) => u.email || t("common.dash"),
      },
      { id: "role", header: t("users.col.role"), cell: (u) => roleLabel(u.role) },
      {
        id: "status",
        header: t("users.col.status"),
        cell: (u) => (
          <StatusBadge
            variant={u.is_active ? "ready" : "stopped"}
            label={u.is_active ? t("users.status.active") : t("users.status.inactive")}
          />
        ),
      },
      {
        id: "last_login",
        header: t("users.col.last_login"),
        cell: (u) =>
          u.last_login_at ? new Date(u.last_login_at).toLocaleString() : t("common.dash"),
      },
      {
        id: "actions",
        header: t("users.col.actions"),
        cell: (u) => (
          <div className="ds-table-actions">
            <Button variant="ghost" size="sm" onClick={() => openEdit(u)}>
              {t("users.edit")}
            </Button>
            <Button variant="ghost" size="sm" onClick={() => openPassword(u)}>
              {t("users.change_password")}
            </Button>
            {u.id !== currentUser?.id ? (
              <>
                <Button variant="ghost" size="sm" onClick={() => void toggleActive(u)}>
                  {u.is_active ? t("users.deactivate") : t("users.activate")}
                </Button>
                <Button variant="danger" size="sm" onClick={() => void onDelete(u)}>
                  {t("users.delete")}
                </Button>
              </>
            ) : null}
          </div>
        ),
      },
    ],
    [t, roleLabel, currentUser?.id]
  );

  const modalTitle =
    mode === "create"
      ? t("users.create")
      : mode === "edit"
        ? t("users.edit")
        : t("users.change_password");

  return (
    <PageLayout>
      <PageHeader
        title={t("users.title")}
        subtitle={t("users.subtitle")}
        actions={
          <Button variant="primary" onClick={openCreate}>
            {t("users.create")}
          </Button>
        }
      />

      {error ? <Alert variant="error">{error}</Alert> : null}

      {loading ? (
        <LoadingState label={t("common.loading")} />
      ) : (
        <DataTable
          columns={columns}
          data={users}
          keyFn={(u) => u.id}
          emptyTitle={t("users.empty")}
        />
      )}

      <Modal
        open={mode !== null}
        title={modalTitle}
        onClose={closeModal}
        actions={
          <>
            <Button variant="secondary" onClick={closeModal}>
              {t("common.close")}
            </Button>
            <Button variant="primary" type="submit" form="users-form" disabled={saving}>
              {saving ? t("common.saving") : t("common.save_generic")}
            </Button>
          </>
        }
      >
        <form id="users-form" onSubmit={onSubmit}>
          <FormStack>
            {mode !== "password" ? (
              <>
                <Field label={t("auth.username")}>
                  <Input value={username} onChange={(e) => setUsername(e.target.value)} required />
                </Field>
                <Field label={t("users.col.display_name")}>
                  <Input value={displayName} onChange={(e) => setDisplayName(e.target.value)} required />
                </Field>
                <Field label={t("users.col.email")}>
                  <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
                </Field>
                <Field label={t("users.col.role")}>
                  <Select value={role} onChange={(e) => setRole(e.target.value as UserRole)}>
                    {ROLES.map((r) => (
                      <option key={r} value={r}>
                        {roleLabel(r)}
                      </option>
                    ))}
                  </Select>
                </Field>
                <CheckboxField
                  label={t("users.status.active")}
                  checked={isActive}
                  onChange={(e) => setIsActive(e.target.checked)}
                />
              </>
            ) : null}
            {mode === "create" || mode === "password" ? (
              <Field label={t("auth.password")}>
                <Input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={4}
                />
              </Field>
            ) : null}
            {formError ? <Alert variant="error">{formError}</Alert> : null}
          </FormStack>
        </form>
      </Modal>
    </PageLayout>
  );
}
