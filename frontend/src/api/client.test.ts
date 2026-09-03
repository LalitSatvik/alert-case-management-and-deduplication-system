import { describe, it, expect, vi } from "vitest";
import { apiFetch, ApiError } from "./client";

describe("apiFetch", () => {
  it("attaches bearer token and parses json", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));
    const r = await apiFetch<{ ok: boolean }>("/cases", { token: "t" });
    expect(r.ok).toBe(true);
    const [, init] = (global.fetch as any).mock.calls[0];
    expect(init.headers.Authorization).toBe("Bearer t");
  });

  it("throws ApiError with status on non-2xx", async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "nope" }), { status: 403 }));
    await expect(apiFetch("/cases")).rejects.toMatchObject({ status: 403 } as ApiError);
  });
});
