import {
  AI_TIMEOUT_MS,
  ApiNetworkError,
  ApiTimeoutError,
  DEFAULT_TIMEOUT_MS,
  apiFetch,
  parseErrorMessage,
} from "@/services/httpClient";
import { getStacks } from "@/services/stacksService";
import { createSession, submitAnswer } from "@/services/sessionService";
import { getCards } from "@/services/cardService";
import { loginUser } from "@/services/authService";

const okJson = (body: unknown) =>
  new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });

// A fetch that never settles on its own and only rejects when its signal aborts.
function hangingFetch() {
  return vi.fn((_url: unknown, init?: RequestInit) =>
    new Promise<Response>((_resolve, reject) => {
      init?.signal?.addEventListener("abort", () => reject(init.signal?.reason));
    })
  );
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("apiFetch timeouts and failure mapping", () => {
  it("rejects with the Spanish timeout error when the request hangs", async () => {
    vi.stubGlobal("fetch", hangingFetch());

    const promise = apiFetch("/slow", { timeoutMs: 20 });

    await expect(promise).rejects.toBeInstanceOf(ApiTimeoutError);
    await expect(promise).rejects.toThrow("La solicitud tardó demasiado. Inténtalo de nuevo.");
  });

  it("maps a network TypeError to the Spanish network error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    const promise = apiFetch("/down");

    await expect(promise).rejects.toBeInstanceOf(ApiNetworkError);
    await expect(promise).rejects.toThrow("No se pudo conectar con el servidor.");
    await expect(promise).rejects.not.toThrow("Failed to fetch");
  });

  it("does not swallow other errors", async () => {
    const boom = new RangeError("boom");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(boom));

    await expect(apiFetch("/x")).rejects.toBe(boom);
  });

  it("keeps a caller abort as an abort, not a timeout", async () => {
    vi.stubGlobal("fetch", hangingFetch());
    const controller = new AbortController();

    const promise = apiFetch("/x", { signal: controller.signal });
    controller.abort();

    const error = await promise.catch((e) => e);
    expect(error).not.toBeInstanceOf(ApiTimeoutError);
    expect(error).not.toBeInstanceOf(ApiNetworkError);
    expect(error.name).toBe("AbortError");
  });

  it("still times out with a caller signal when AbortSignal.any is unavailable", async () => {
    vi.stubGlobal("fetch", hangingFetch());
    const original = Object.getOwnPropertyDescriptor(AbortSignal, "any")!;
    Object.defineProperty(AbortSignal, "any", { value: undefined, configurable: true });
    try {
      const controller = new AbortController();
      await expect(apiFetch("/x", { signal: controller.signal, timeoutMs: 20 })).rejects.toBeInstanceOf(
        ApiTimeoutError
      );
    } finally {
      Object.defineProperty(AbortSignal, "any", original);
    }
  });

  it("still times out when AbortSignal.timeout is unavailable (older browsers)", async () => {
    vi.stubGlobal("fetch", hangingFetch());
    const original = Object.getOwnPropertyDescriptor(AbortSignal, "timeout")!;
    Object.defineProperty(AbortSignal, "timeout", { value: undefined, configurable: true });
    try {
      await expect(apiFetch("/x", { timeoutMs: 20 })).rejects.toBeInstanceOf(ApiTimeoutError);

      const controller = new AbortController();
      const withCaller = apiFetch("/x", { signal: controller.signal, timeoutMs: 20 });
      await expect(withCaller).rejects.toBeInstanceOf(ApiTimeoutError);
    } finally {
      Object.defineProperty(AbortSignal, "timeout", original);
    }
  });

  it("keeps a caller abort an abort when AbortSignal.timeout is unavailable", async () => {
    vi.stubGlobal("fetch", hangingFetch());
    const original = Object.getOwnPropertyDescriptor(AbortSignal, "timeout")!;
    Object.defineProperty(AbortSignal, "timeout", { value: undefined, configurable: true });
    try {
      const controller = new AbortController();
      const promise = apiFetch("/x", { signal: controller.signal });
      controller.abort();
      const error = await promise.catch((e) => e);
      expect(error).not.toBeInstanceOf(ApiTimeoutError);
      expect(error).not.toBeInstanceOf(ApiNetworkError);
      expect(error.name).toBe("AbortError");
    } finally {
      Object.defineProperty(AbortSignal, "timeout", original);
    }
  });

  it("uses the default timeout unless the caller overrides it", async () => {
    const timeoutSpy = vi.spyOn(AbortSignal, "timeout");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(okJson({})));

    await apiFetch("/a");
    await apiFetch("/b", { timeoutMs: 1234 });

    expect(DEFAULT_TIMEOUT_MS).toBe(15_000);
    expect(timeoutSpy).toHaveBeenNthCalledWith(1, DEFAULT_TIMEOUT_MS);
    expect(timeoutSpy).toHaveBeenNthCalledWith(2, 1234);
  });
});

describe("AI endpoints use the longer timeout", () => {
  it("createSession and submitAnswer use AI_TIMEOUT_MS, other endpoints the default", async () => {
    const timeoutSpy = vi.spyOn(AbortSignal, "timeout");
    vi.stubGlobal("fetch", vi.fn().mockImplementation(() => Promise.resolve(okJson([]))));

    await createSession({ stack: "python", level: "junior", topic: "x" });
    await submitAnswer(1, 2, "respuesta");
    await getCards();

    expect(AI_TIMEOUT_MS).toBe(60_000);
    expect(timeoutSpy.mock.calls.map((c) => c[0])).toEqual([AI_TIMEOUT_MS, AI_TIMEOUT_MS, DEFAULT_TIMEOUT_MS]);
  });
});

describe("getStacks", () => {
  it("goes through apiFetch, which never sends cookies", async () => {
    const fetchMock = vi.fn().mockResolvedValue(okJson({ rol: {}, level: [], topic: {} }));
    vi.stubGlobal("fetch", fetchMock);

    await getStacks();

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/stacks/");
    expect(init.credentials).toBeUndefined();
    expect(init.signal).toBeInstanceOf(AbortSignal);
  });
});

describe("parseErrorMessage", () => {
  it("reads the message from a JSON error body", async () => {
    const response = new Response(JSON.stringify({ error: "Credenciales inválidas" }), { status: 401 });
    await expect(parseErrorMessage(response)).resolves.toBe("Credenciales inválidas");
  });

  it("falls back to status text for a non-JSON body", async () => {
    const response = new Response("<html>Bad Gateway</html>", { status: 502, statusText: "Bad Gateway" });
    await expect(parseErrorMessage(response)).resolves.toBe("Error 502: Bad Gateway");
  });

  it("falls back to status text for an empty body", async () => {
    const response = new Response(null, { status: 500, statusText: "Internal Server Error" });
    await expect(parseErrorMessage(response)).resolves.toBe("Error 500: Internal Server Error");
  });

  it("falls back when the JSON body carries no known message field", async () => {
    const response = new Response(JSON.stringify({ detail: "x" }), { status: 400, statusText: "Bad Request" });
    await expect(parseErrorMessage(response)).resolves.toBe("Error 400: Bad Request");
  });

  it("is the parser authService uses (no duplicate copy)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ msg: "Correo no verificado" }), { status: 403 }))
    );
    await expect(loginUser("a@b.c", "pw")).rejects.toThrow("Correo no verificado");

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("nope", { status: 500, statusText: "Oops" })));
    await expect(loginUser("a@b.c", "pw")).rejects.toThrow("Error 500: Oops");
  });
});
