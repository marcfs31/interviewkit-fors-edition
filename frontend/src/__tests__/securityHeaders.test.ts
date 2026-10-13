import { buildSecurityHeaders } from "../lib/securityHeaders.mjs";

const API_URL = "https://interview-prep-api.fly.dev";
const API_ORIGIN = "https://interview-prep-api.fly.dev";

type Header = { key: string; value: string };

function headerValue(headers: Header[], key: string): string | undefined {
  return headers.find((h) => h.key.toLowerCase() === key.toLowerCase())?.value;
}

function directives(csp: string): Record<string, string[]> {
  const out: Record<string, string[]> = {};
  for (const part of csp.split(";")) {
    const [name, ...values] = part.trim().split(/\s+/);
    if (name) out[name] = values;
  }
  return out;
}

function prodCsp(apiUrl: string = API_URL): string {
  return headerValue(buildSecurityHeaders({ apiUrl, isDev: false }), "Content-Security-Policy")!;
}

function devCsp(apiUrl: string = API_URL): string {
  return headerValue(buildSecurityHeaders({ apiUrl, isDev: true }), "Content-Security-Policy")!;
}

describe("buildSecurityHeaders: production policy", () => {
  it("connect-src contains exactly 'self' and the API origin", () => {
    expect(directives(prodCsp())["connect-src"]).toEqual(["'self'", API_ORIGIN]);
  });

  it("reduces the API URL to its origin (no path, no trailing slash)", () => {
    const csp = prodCsp("https://interview-prep-api.fly.dev/api/v1/");
    expect(directives(csp)["connect-src"]).toEqual(["'self'", API_ORIGIN]);
  });

  it("has no wildcard anywhere", () => {
    expect(prodCsp()).not.toContain("*");
    expect(devCsp()).not.toContain("*");
  });

  it("locks down objects and framing", () => {
    const d = directives(prodCsp());
    expect(d["object-src"]).toEqual(["'none'"]);
    expect(d["frame-ancestors"]).toEqual(["'none'"]);
    expect(d["base-uri"]).toEqual(["'self'"]);
    expect(d["form-action"]).toEqual(["'self'"]);
    expect(d["default-src"]).toEqual(["'self'"]);
  });

  it("has no 'unsafe-eval' and keeps inline scripts for the static pages", () => {
    const d = directives(prodCsp());
    expect(prodCsp()).not.toContain("'unsafe-eval'");
    expect(d["script-src"]).toEqual(["'self'", "'unsafe-inline'"]);
    expect(d["style-src"]).toEqual(["'self'", "'unsafe-inline'"]);
  });

  it("limits images and fonts to self plus inline data/blob", () => {
    const d = directives(prodCsp());
    expect(d["img-src"]).toEqual(["'self'", "data:", "blob:"]);
    expect(d["font-src"]).toEqual(["'self'", "data:"]);
  });

  it("upgrades insecure requests and does not allow ws:", () => {
    const csp = prodCsp();
    expect(csp.split(";").map((p) => p.trim())).toContain("upgrade-insecure-requests");
    expect(csp).not.toContain("ws:");
  });

  it("privacy: the only non-'self' host in the whole policy is the API origin", () => {
    const hosts = new Set<string>();
    for (const [name, values] of Object.entries(directives(prodCsp()))) {
      if (name === "upgrade-insecure-requests") continue;
      for (const value of values) {
        const isKeyword = value.startsWith("'") && value.endsWith("'");
        const isScheme = /^[a-z][a-z0-9+.-]*:$/.test(value);
        if (!isKeyword && !isScheme) hosts.add(value);
      }
    }
    expect([...hosts]).toEqual([API_ORIGIN]);
  });

  it("sends the companion security headers, with HSTS", () => {
    const headers = buildSecurityHeaders({ apiUrl: API_URL, isDev: false });
    expect(headerValue(headers, "X-Content-Type-Options")).toBe("nosniff");
    expect(headerValue(headers, "Referrer-Policy")).toBe("strict-origin-when-cross-origin");
    expect(headerValue(headers, "X-Frame-Options")).toBe("DENY");
    expect(headerValue(headers, "Permissions-Policy")).toBe("camera=(), microphone=(), geolocation=()");
    expect(headerValue(headers, "Strict-Transport-Security")).toBe("max-age=63072000; includeSubDomains");
  });
});

describe("buildSecurityHeaders: fail loud", () => {
  it.each([undefined, "", "   "])("throws without an apiUrl in production (%j)", (apiUrl) => {
    expect(() => buildSecurityHeaders({ apiUrl, isDev: false })).toThrow(/NEXT_PUBLIC_API_URL/);
  });

  it.each(["not-a-url", "/relative/path", "interview-prep-api.fly.dev", "javascript:alert(1)", "ftp://example.com"])(
    "throws on an invalid absolute URL (%s)",
    (apiUrl) => {
      expect(() => buildSecurityHeaders({ apiUrl, isDev: false })).toThrow(/NEXT_PUBLIC_API_URL/);
      expect(() => buildSecurityHeaders({ apiUrl, isDev: true })).toThrow(/NEXT_PUBLIC_API_URL/);
    },
  );
});

describe("buildSecurityHeaders: development policy", () => {
  it("adds ws: for HMR and 'unsafe-eval' for React dev", () => {
    const d = directives(devCsp());
    expect(d["connect-src"]).toEqual(["'self'", API_ORIGIN, "ws:"]);
    expect(d["script-src"]).toContain("'unsafe-eval'");
  });

  it("keeps object-src and frame-ancestors locked down", () => {
    const d = directives(devCsp());
    expect(d["object-src"]).toEqual(["'none'"]);
    expect(d["frame-ancestors"]).toEqual(["'none'"]);
  });

  it("omits HSTS and upgrade-insecure-requests", () => {
    const headers = buildSecurityHeaders({ apiUrl: API_URL, isDev: true });
    expect(headerValue(headers, "Strict-Transport-Security")).toBeUndefined();
    expect(devCsp()).not.toContain("upgrade-insecure-requests");
  });

  it("without an apiUrl allows only 'self' (never every origin)", () => {
    const headers = buildSecurityHeaders({ apiUrl: undefined, isDev: true });
    const d = directives(headerValue(headers, "Content-Security-Policy")!);
    expect(d["connect-src"]).toEqual(["'self'", "ws:"]);
  });
});
