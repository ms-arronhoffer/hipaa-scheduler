import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import ProtectedRoute from "../ProtectedRoute";

// Stub AuthContext.useAuth so this test isolates routing behavior from
// the network / token side-effects exercised in client.test.ts.
vi.mock("../AuthContext", () => ({
  useAuth: vi.fn(),
}));

import { useAuth } from "../AuthContext";
const mockUseAuth = vi.mocked(useAuth);

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route element={<ProtectedRoute />}>
          <Route path="/secret" element={<div>secret content</div>} />
        </Route>
        <Route path="/login" element={<div>login page</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ProtectedRoute", () => {
  it("redirects unauthenticated users to /login", () => {
    mockUseAuth.mockReturnValue({
      user: null,
      loading: false,
      isAuthenticated: false,
    } as never);
    renderAt("/secret");
    expect(screen.getByText("login page")).toBeInTheDocument();
    expect(screen.queryByText("secret content")).not.toBeInTheDocument();
  });

  it("renders the protected outlet when authenticated", () => {
    mockUseAuth.mockReturnValue({
      user: { id: "u1", roles: ["provider"], is_super_admin: false },
      loading: false,
      isAuthenticated: true,
    } as never);
    renderAt("/secret");
    expect(screen.getByText("secret content")).toBeInTheDocument();
  });

  it("shows a spinner (not the outlet or login) while auth is loading", () => {
    mockUseAuth.mockReturnValue({
      user: null,
      loading: true,
      isAuthenticated: false,
    } as never);
    const { container } = renderAt("/secret");
    expect(screen.queryByText("secret content")).not.toBeInTheDocument();
    expect(screen.queryByText("login page")).not.toBeInTheDocument();
    // Cloudscape Spinner renders an svg — the outer wrapper is present.
    expect(container.querySelector("svg")).not.toBeNull();
  });
});
