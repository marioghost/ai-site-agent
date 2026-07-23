import { StatusBadge, healthStatusToBadge } from "../../ui";

interface Props {
  status: string;
  label: string;
  size?: "sm" | "md";
}

export default function StatusIndicator({ status, label, size = "md" }: Props) {
  return (
    <StatusBadge variant={healthStatusToBadge(status)} label={label} size={size} />
  );
}

export { healthStatusToBadge as statusToVariant };
