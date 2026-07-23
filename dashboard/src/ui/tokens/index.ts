/** Design token constants (mirror CSS custom properties). */
export const colors = {
  accent: "#5B5BD6",
  accentHover: "#4F46E5",
  accentSoft: "rgba(91, 91, 214, 0.08)",
  success: "#16A34A",
  successSoft: "rgba(22, 163, 74, 0.1)",
  warning: "#D97706",
  warningSoft: "rgba(217, 119, 6, 0.1)",
  danger: "#DC2626",
  dangerSoft: "rgba(220, 38, 38, 0.08)",
  info: "#2563EB",
  infoSoft: "rgba(37, 99, 235, 0.08)",
  neutral: "#64748B",
  neutralSoft: "rgba(100, 116, 139, 0.1)",
  bg: "#F8F9FB",
  surface: "#FFFFFF",
  surfaceMuted: "#F4F6F8",
  border: "#E5E8ED",
  borderSoft: "#EEF1F5",
  text: "#111827",
  textSecondary: "#4B5563",
  textMuted: "#6B7280",
} as const;

export const spacing = {
  0: "0",
  1: "4px",
  2: "8px",
  3: "12px",
  4: "16px",
  5: "20px",
  6: "24px",
  8: "32px",
  10: "40px",
  12: "48px",
  16: "64px",
} as const;

export const radii = {
  sm: "8px",
  md: "12px",
  lg: "16px",
  full: "9999px",
} as const;

export const shadows = {
  xs: "0 1px 2px rgba(17, 24, 39, 0.04)",
  sm: "0 1px 3px rgba(17, 24, 39, 0.06), 0 1px 2px rgba(17, 24, 39, 0.04)",
  md: "0 4px 16px rgba(17, 24, 39, 0.07), 0 2px 4px rgba(17, 24, 39, 0.04)",
} as const;

export const typography = {
  display: { size: "36px", lineHeight: "44px", weight: 600 },
  pageTitle: { size: "28px", lineHeight: "36px", weight: 600 },
  sectionTitle: { size: "18px", lineHeight: "26px", weight: 600 },
  cardTitle: { size: "15px", lineHeight: "22px", weight: 600 },
  body: { size: "14px", lineHeight: "22px", weight: 400 },
  bodyLg: { size: "15px", lineHeight: "24px", weight: 400 },
  caption: { size: "12px", lineHeight: "18px", weight: 400 },
  tiny: { size: "11px", lineHeight: "16px", weight: 500 },
} as const;

export const motion = {
  fast: "150ms",
  normal: "200ms",
  slow: "250ms",
  ease: "cubic-bezier(0.4, 0, 0.2, 1)",
} as const;

export const layout = {
  sidebarWidth: "248px",
  sidebarCollapsedWidth: "72px",
  topbarHeight: "56px",
  contentMaxWidth: "none",
  pageGutter: "20px",
  pageGap: "24px",
  contentPaddingY: "24px",
  cardPadding: "24px",
  controlHeight: "36px",
} as const;

export const zIndex = {
  base: 0,
  dropdown: 100,
  sticky: 200,
  sidebar: 300,
  modal: 400,
  toast: 500,
} as const;

export const icons = {
  sm: "16px",
  md: "20px",
  lg: "24px",
  stroke: 1.75,
} as const;
