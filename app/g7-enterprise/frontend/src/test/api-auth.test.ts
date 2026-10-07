import { afterEach, describe, expect, it, vi } from "vitest";
import * as api from "../api";

const originalCreate = Object.getOwnPropertyDescriptor(URL, "createObjectURL");
const originalRevoke = Object.getOwnPropertyDescriptor(URL, "revokeObjectURL");

afterEach(() => {
  api.setToken(null);
  api.setProject(null);
  vi.restoreAllMocks();
  if (originalCreate) Object.defineProperty(URL, "createObjectURL", originalCreate);
  else Reflect.deleteProperty(URL, "createObjectURL");
  if (originalRevoke) Object.defineProperty(URL, "revokeObjectURL", originalRevoke);
  else Reflect.deleteProperty(URL, "revokeObjectURL");
});

describe("authenticated media and exports", () => {
  it("clears the session and requests sign-in once when authenticated bytes expire", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("expired", { status: 401 })));
    const expired = vi.fn();
    window.addEventListener("osteopatch:session-expired", expired);
    api.setToken("expired-token"); api.setProject("prj_demo");
    try {
      await expect(api.blobUrl("/v1/images/a/full")).rejects.toThrow("401");
      await expect(api.downloadReviews("csv")).rejects.toThrow("401");
      expect(expired).toHaveBeenCalledTimes(1);
      expect(api.getProject()).toBeNull();
    } finally { window.removeEventListener("osteopatch:session-expired", expired); }
  });
  it("requests image bytes with bearer and project headers, never URL credentials", async () => {
    const fetchMock = vi.fn(async () => new Response(new Blob(["png"]), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    Object.defineProperty(URL, "createObjectURL", { configurable: true, value: () => "blob:media" });
    api.setToken("secret-token");
    api.setProject("prj_demo");

    await api.blobUrl("/v1/images/patch-a/thumbnail");

    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/v1/images/patch-a/thumbnail");
    expect(url).not.toContain("secret-token");
    expect(init.headers).toMatchObject({ Authorization: "Bearer secret-token", "X-Project-Id": "prj_demo" });
  });

  it("downloads exports through the authenticated API client", async () => {
    const fetchMock = vi.fn(async () => new Response("csv", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    Object.defineProperty(URL, "createObjectURL", { configurable: true, value: () => "blob:export" });
    Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: vi.fn() });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    api.setToken("secret-token");
    api.setProject("prj_demo");

    await api.downloadReviews("csv");

    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/v1/exports/reviews?format=csv");
    expect(url).not.toContain("secret-token");
    expect(init.headers).toMatchObject({ Authorization: "Bearer secret-token", "X-Project-Id": "prj_demo" });
    expect(HTMLAnchorElement.prototype.click).toHaveBeenCalledTimes(1);
    await new Promise((resolve) => window.setTimeout(resolve, 5));
  });
});
