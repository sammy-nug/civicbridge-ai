// All backend calls go through here, so errors reach the UI in one consistent, friendly form.
const BASE_URL = import.meta.env.VITE_API_BASE_URL || "";
const TIMEOUT_MS = 120000;

export class ApiError extends Error {
  constructor(message, code, status) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

async function request(path, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const response = await fetch(`${BASE_URL}${path}`, {
      ...options,
      signal: controller.signal,
      headers: options.body ? { "Content-Type": "application/json" } : undefined,
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      throw new ApiError(
        data?.error?.message || "Something went wrong. Please try again.",
        data?.error?.code || "error",
        response.status
      );
    }
    return data;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error.name === "AbortError") {
      throw new ApiError("This is taking too long. Your connection may be slow. Please try again.", "timeout", 0);
    }
    throw new ApiError("We can't reach the server. Check your internet connection and try again.", "network", 0);
  } finally {
    clearTimeout(timer);
  }
}

const post = (path, body) => request(path, { method: "POST", body: JSON.stringify(body) });

export const sendChat = (message, language, sessionId) =>
  post("/api/chat", { message, language, ...(sessionId ? { session_id: sessionId } : {}) });
export const verifyClaim = (claim, language) => post("/api/verify", { claim, language });
export const sendFeedback = (responseId, rating, feedback) =>
  post("/api/feedback", { response_id: responseId, rating, ...(feedback ? { feedback } : {}) });
export const getResources = () => request("/api/resources");
export const getHealth = () => request("/api/health");
