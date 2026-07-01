import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { RoleGuard } from "../RoleGuard";

vi.mock("../AuthContext", () => ({ useAuth: vi.fn() }));
import { useAuth } from "../AuthContext";
const mockUseAuth = vi.mocked(useAuth);

function withUser(user: unknown) {
  mockUseAuth.mockReturnValue({ user, isAuthenticated: !!user, loading: false } as never);
}

describe("RoleGuard", () => {
  it("shows children when user role is in the allow-list", () => {
    withUser({ id: "u", roles: ["provider"], is_super_admin: false });
    render(<RoleGuard roles={["provider", "front_desk"]}>ok</RoleGuard>);
    expect(screen.getByText("ok")).toBeInTheDocument();
  });

  it("hides children when user has no matching role", () => {
    withUser({ id: "u", roles: ["billing"], is_super_admin: false });
    render(<RoleGuard roles={["provider"]}>ok</RoleGuard>);
    expect(screen.queryByText("ok")).not.toBeInTheDocument();
  });

  it("super_admin bypasses the role check", () => {
    withUser({ id: "u", roles: [], is_super_admin: true });
    render(<RoleGuard roles={["provider"]}>ok</RoleGuard>);
    expect(screen.getByText("ok")).toBeInTheDocument();
  });

  it("renders fallback when no user is present", () => {
    withUser(null);
    render(
      <RoleGuard roles={["provider"]} fallback={<span>fallback</span>}>
        ok
      </RoleGuard>,
    );
    expect(screen.getByText("fallback")).toBeInTheDocument();
    expect(screen.queryByText("ok")).not.toBeInTheDocument();
  });
});
