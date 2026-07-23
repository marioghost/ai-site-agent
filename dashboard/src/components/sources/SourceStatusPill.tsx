import { StatusBadge, statusToVariant } from "../../ui";
import type { StatusVariant } from "../../ui";
import { displayStatusKey } from "./sourceUtils";

type Props = {
  status: string | null | undefined;
  label: string;
  size?: "sm" | "md";
};

const BUCKET_VARIANT: Record<string, StatusVariant> = {
  ready: "ready",
  pending: "pending",
  failed: "failed",
  skipped: "skipped",
  needs_refresh: "needs_refresh",
};

export default function SourceStatusPill({ status, label, size = "sm" }: Props) {
  const key = displayStatusKey(status);
  const variant = BUCKET_VARIANT[key] ?? statusToVariant(status ?? "pending");
  return <StatusBadge variant={variant} label={label} size={size} />;
}
