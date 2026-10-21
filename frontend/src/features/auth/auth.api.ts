
import { apiRequest } from "../../api/client";

export interface CurrentUser {
  id: string;
}

export function exchangeLoginToken(
  token: string,
): Promise<{ message: string }> {
  return apiRequest("/auth/exchange", {
    method: "POST",
    body: JSON.stringify({ token }),
  });
}

export function logout(): Promise<{ message: string }> {
  return apiRequest("/auth/logout", {
    method: "POST",
  });
}

export function getCurrentUser(): Promise<CurrentUser> {
  return apiRequest("/auth/me");
}
