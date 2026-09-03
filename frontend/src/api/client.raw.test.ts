import { describe, it, expect, vi } from "vitest";
import { apiFetch, ApiError, setRefreshHandler } from "./client";

describe("apiFetch raw option", () => {
  it("returns a 2xx text/html body verbatim without JSON.parse", async () => {
    setRefreshHandler(null);
    const html = "<!doctype html><html><body>audit</body></html>";
    global.fetch = vi.fn().mockResolvedValue(
      new Response(html, { status: 200, headers: { "Content-Type": "text/html" } }),
    );
    const r = await apiFetch<string>("/cases/1/audit:export?format=html", {
      method: "POST",
      body: {},
      raw: true,
    });
    expect(r).toBe(html);
  });

  it("still throws ApiError on a non-2xx even with raw", async () => {
    setRefreshHandler(null);
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "boom" }), { status: 500 }),
    );
    await expect(apiFetch("/x", { raw: true })).rejects.toBeInstanceOf(ApiError);
  });
});
