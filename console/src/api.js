/*
 * ADR-051: the Console talks to the same THUTOra API as the school apps, but
 * only to /console/... with its own token. VITE_API_BASE_URL is set at build
 * time for production (console/.env.production).
 */
const API = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

function message(detail, fallback) {
  if (!detail) return fallback;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => d.msg || String(d)).join("; ");
  return fallback;
}

let onSessionEnded = () => {};
export function setSessionEndedHandler(fn) {
  onSessionEnded = fn;
}

export async function call(path, { token, method = "GET", body } = {}) {
  let res;
  try {
    res = await fetch(`${API}/console${path}`, {
      method,
      headers: {
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError("Can't reach THUTOra. Check your connection.", 0);
  }
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    // a full session that has ended (not a wrong password on the sign-in screen)
    if (res.status === 401 && token && !path.startsWith("/auth/verify")) onSessionEnded();
    throw new ApiError(message(data.detail, `Something went wrong (${res.status}).`), res.status);
  }
  return data;
}
