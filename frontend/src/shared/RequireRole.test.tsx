import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("./auth", () => ({ useAuth: vi.fn() }));

import { useAuth } from "./auth";
import { RequireRole } from "./RequireRole";
import { MANAGE_ROLES } from "./roles";

afterEach(cleanup);

function renderAt(role: string | null) {
  (useAuth as unknown as { mockReturnValue: (v: unknown) => void }).mockReturnValue({
    user: role ? { role } : null,
    isLoading: false,
  });
  return render(
    <MemoryRouter initialEntries={["/products"]}>
      <Routes>
        <Route
          path="/products"
          element={
            <RequireRole roles={MANAGE_ROLES}>
              <div>PRODUCTS</div>
            </RequireRole>
          }
        />
        <Route path="/pos" element={<div>POS</div>} />
      </Routes>
    </MemoryRouter>
  );
}

describe("RequireRole (защита маршрута)", () => {
  it("кассира уводит с /products на /pos", () => {
    renderAt("cashier");
    expect(screen.queryByText("PRODUCTS")).toBeNull();
    expect(screen.getByText("POS")).toBeTruthy();
  });

  it("менеджер видит /products", () => {
    renderAt("manager");
    expect(screen.getByText("PRODUCTS")).toBeTruthy();
  });
});
