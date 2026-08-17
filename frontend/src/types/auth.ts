export interface User {
  id: number;
  username: string;
  displayName: string;
  role: string;
  isActive: boolean;
  createdAt: string | null;
  updatedAt?: string | null;
  lastLoginAt: string | null;
}

export interface AuthResponse {
  success: true;
  user?: User;
  message?: string;
  csrfToken?: string;
  requestId: string;
}

export interface LoginInput {
  username: string;
  password: string;
  remember: boolean;
}

export interface RegisterInput {
  username: string;
  displayName: string;
  password: string;
}
