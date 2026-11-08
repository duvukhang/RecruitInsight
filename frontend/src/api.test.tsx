import { describe, it, expect, vi, afterEach } from "vitest";
afterEach(() => {
  vi.unstubAllGlobals();
  vi.resetModules();
  sessionStorage.clear();
});
describe("token refresh", () => {
  it("shares one refresh across concurrent unauthorized requests and retries with the new token", async () => {
    const calls: Record<string, number> = {};
    const fetcher = vi.fn(async (url: string, init: RequestInit) => {
      calls[url] = (calls[url] || 0) + 1;
      if (url.endsWith("/auth/refresh")) {
        await new Promise((resolve) => setTimeout(resolve, 15));
        return new Response(
          JSON.stringify({
            data: { access_token: "fixture-new" },
            csrf_token: "fixture-csrf-new",
          }),
          { headers: { "Content-Type": "application/json" } },
        );
      }
      if (calls[url] === 1)
        return new Response("{}", {
          status: 401,
          headers: { "Content-Type": "application/json" },
        });
      expect((init.headers as Record<string, string>).Authorization).toBe(
        "Bearer fixture-new",
      );
      return new Response('{"data":[]}', {
        headers: { "Content-Type": "application/json" },
      });
    });
    vi.stubGlobal("fetch", fetcher);
    const { api, remember } = await import("./api");
    remember({
      data: { access_token: "fixture-old" },
      csrf_token: "fixture-csrf",
    });
    await Promise.all([api("/jobs"), api("/datasets"), api('/auth/profile')]);
    expect(calls["/api/v1/auth/refresh"]).toBe(1);
    expect(calls["/api/v1/jobs"]).toBe(2);
    expect(calls["/api/v1/datasets"]).toBe(2);
    expect(calls['/api/v1/auth/profile']).toBe(2);
  });
});
