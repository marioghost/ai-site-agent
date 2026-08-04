import type { UserRole } from "../types";

/**
 * RFC-101 §2.1 role × route access (product + engineering).
 * Codebase roles: admin ≈ Owner, operator ≈ Operator, viewer ≈ Viewer.
 */
const ROUTE_ROLES: Record<string, UserRole[]> = {
  // Legacy (coexistence)
  "/overview": ["admin", "operator", "viewer"],
  "/indexing": ["admin", "operator"],
  "/sources": ["admin", "operator"],
  "/chat": ["admin", "operator"],
  "/analytics": ["admin", "operator", "viewer"],
  "/logs": ["admin", "operator", "viewer"],
  "/knowledge-profile": ["admin"],
  "/understanding": ["admin"],
  "/diagnostics/epistemic-health": ["admin"],
  "/users": ["admin"],
  // Canonical product
  "/home": ["admin", "operator", "viewer"],
  "/knowledge": ["admin", "operator"],
  "/knowledge/library": ["admin", "operator"],
  "/knowledge/update": ["admin", "operator"],
  "/knowledge/site": ["admin", "operator"],
  "/ask": ["admin", "operator"],
  "/insights": ["admin", "operator", "viewer"],
  "/insights/performance": ["admin", "operator", "viewer"],
  "/insights/activity": ["admin", "operator", "viewer"],
  "/settings": ["admin"],
  "/settings/general": ["admin"],
  "/settings/models": ["admin"],
  "/settings/answers": ["admin"],
  "/settings/access": ["admin"],
  // Engineering (Owner/admin + Mode on enforced by guard)
  "/engineering": ["admin"],
  "/engineering/status": ["admin"],
  "/engineering/ask-details": ["admin"],
  "/engineering/knowledge": ["admin"],
  "/engineering/tensions": ["admin"],
  "/engineering/advanced": ["admin"],
  "/engineering/build": ["admin"],
};

export function canAccessRoute(role: UserRole, path: string): boolean {
  const normalized = path.split("?")[0].replace(/\/$/, "") || "/";
  const allowed = ROUTE_ROLES[normalized];
  if (!allowed) {
    // Prefix match for nested paths
    const match = Object.keys(ROUTE_ROLES)
      .filter((k) => normalized === k || normalized.startsWith(`${k}/`))
      .sort((a, b) => b.length - a.length)[0];
    if (!match) return true;
    return ROUTE_ROLES[match].includes(role);
  }
  return allowed.includes(role);
}

export function roleLabelKey(role: UserRole): string {
  return `users.role.${role}`;
}

export function isEngineeringPath(path: string): boolean {
  const normalized = path.split("?")[0];
  return normalized === "/engineering" || normalized.startsWith("/engineering/");
}
