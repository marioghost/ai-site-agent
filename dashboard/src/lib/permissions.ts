import type { UserRole } from "../types";

const ROUTE_ROLES: Record<string, UserRole[]> = {
  "/overview": ["admin", "operator", "viewer"],
  "/indexing": ["admin", "operator"],
  "/sources": ["admin", "operator"],
  "/chat": ["admin", "operator"],
  "/analytics": ["admin", "operator", "viewer"],
  "/logs": ["admin", "operator", "viewer"],
  "/knowledge-profile": ["admin"],
  "/understanding": ["admin"],
  "/diagnostics/epistemic-health": ["admin"],
  "/settings": ["admin"],
  "/users": ["admin"],
};

export function canAccessRoute(role: UserRole, path: string): boolean {
  const allowed = ROUTE_ROLES[path];
  if (!allowed) return true;
  return allowed.includes(role);
}

export function roleLabelKey(role: UserRole): string {
  return `users.role.${role}`;
}
