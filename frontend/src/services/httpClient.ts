const API_URL = process.env.NEXT_PUBLIC_API_URL;

export function headers(): Record<string, string> {
  const h: Record<string, string>= { "Content-Type": "application/json" };
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("access_token");
    if (token) {
      h["Authorization"] = `Bearer ${token}`;
    }
  }
  return h;
}

let onUnauthorizedCallback: (()=>void) | null = null;

export function setOnUnauthorized(cb: (()=>void)) {
  onUnauthorizedCallback = cb;
}

export async function handleResponse<T>(response: Response): Promise<T> {
  if (response.ok) {
    return response.json();
  }

  if (response.status === 401) {
    if (onUnauthorizedCallback) {
      onUnauthorizedCallback();
    }
    throw new Error("Tu sesión ha expirado. Inicia sesión de nuevo.");
  }

  throw new Error(await parseErrorMessage(response));
}

// Single owner of the error-body format: every service reads failures through here.
export async function parseErrorMessage(response: Response): Promise<string> {
  let errorMsg;
  try {
    const data = await response.json();
    errorMsg = data.error || data.Error || data.msg || data.message;
  } catch {
    errorMsg = null;
  }

  return errorMsg || `Error ${response.status}: ${response.statusText}`;
}

export const DEFAULT_TIMEOUT_MS = 15_000;
// Backend worst case for an AI call is about 40 s.
export const AI_TIMEOUT_MS = 60_000;

export class ApiTimeoutError extends Error {
  constructor() {
    super("La solicitud tardó demasiado. Inténtalo de nuevo.");
    this.name = "ApiTimeoutError";
  }
}

export class ApiNetworkError extends Error {
  constructor() {
    super("No se pudo conectar con el servidor.");
    this.name = "ApiNetworkError";
  }
}

function timeoutSignal(timeoutMs: number): AbortSignal {
  if (typeof AbortSignal.timeout === "function") return AbortSignal.timeout(timeoutMs);

  // AbortSignal.timeout is missing before Chrome 103 / Firefox 100 / Safari 16, which we still build for.
  const controller = new AbortController();
  setTimeout(() => controller.abort(new DOMException("The operation timed out.", "TimeoutError")), timeoutMs);
  return controller.signal;
}

function withTimeout(timeoutMs: number, callerSignal?: AbortSignal | null): AbortSignal {
  const timeout = timeoutSignal(timeoutMs);
  if (!callerSignal) return timeout;
  if (typeof AbortSignal.any === "function") return AbortSignal.any([callerSignal, timeout]);

  // Browsers without AbortSignal.any: forward whichever signal fires first.
  const controller = new AbortController();
  for (const signal of [callerSignal, timeout]) {
    if (signal.aborted) {
      controller.abort(signal.reason);
      break;
    }
    signal.addEventListener("abort", () => controller.abort(signal.reason), { once: true });
  }
  return controller.signal;
}

export async function apiFetch(
  url: string,
  options: RequestInit & { timeoutMs?: number } = {}
): Promise<Response> {
  const { headers: customHeaders, timeoutMs = DEFAULT_TIMEOUT_MS, signal, ...rest } = options;
  // Built outside the try so an unexpected failure here is not reported as a network error.
  const combinedSignal = withTimeout(timeoutMs, signal);
  try {
    return await fetch(`${API_URL}${url}`, {
      ...rest,
      signal: combinedSignal,
      headers: {
        ...headers(),
        ...customHeaders,
      },
    });
  } catch (error) {
    // Matched by name: a DOMException can come from another realm and fail instanceof Error.
    if ((error as { name?: unknown } | null)?.name === "TimeoutError") throw new ApiTimeoutError();
    if (error instanceof TypeError) throw new ApiNetworkError();
    throw error;
  }
}

export { API_URL };