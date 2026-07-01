import { describe, expect, it } from "vitest";
import {
  clearTokens,
  getRefreshToken,
  getToken,
  setRefreshToken,
  setToken,
} from "../client";

describe("token storage", () => {
  it("persists an access token in sessionStorage", () => {
    setToken("abc.def.ghi");
    expect(getToken()).toBe("abc.def.ghi");
    expect(window.sessionStorage.getItem("hs_access_token")).toBe("abc.def.ghi");
  });

  it("does NOT use localStorage (XSS surface)", () => {
    setToken("abc.def.ghi");
    setRefreshToken("refresh");
    expect(window.localStorage.length).toBe(0);
  });

  it("returns null when no token stored", () => {
    expect(getToken()).toBeNull();
    expect(getRefreshToken()).toBeNull();
  });

  it("clearTokens removes both keys", () => {
    setToken("a");
    setRefreshToken("r");
    clearTokens();
    expect(getToken()).toBeNull();
    expect(getRefreshToken()).toBeNull();
  });

  it("setToken(null) removes the entry", () => {
    setToken("x");
    setToken(null);
    expect(window.sessionStorage.getItem("hs_access_token")).toBeNull();
  });
});
