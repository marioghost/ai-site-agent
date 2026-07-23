export type UserRole = "admin" | "operator" | "viewer";

export interface AuthUser {
  id: number;
  username: string;
  display_name: string;
  role: UserRole;
  email?: string | null;
}

export interface AuthLoginResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

export interface UserRecord {
  id: number;
  username: string;
  email: string | null;
  display_name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
  last_login_at: string | null;
}

export interface UserCreatePayload {
  username: string;
  email?: string | null;
  display_name: string;
  password: string;
  role: UserRole;
  is_active?: boolean;
}

export interface UserUpdatePayload {
  username?: string;
  email?: string | null;
  display_name?: string;
  role?: UserRole;
  is_active?: boolean;
}
