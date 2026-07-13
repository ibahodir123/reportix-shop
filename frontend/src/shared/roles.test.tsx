import { describe, expect, it } from "vitest";

import { canAccess, visibleNav } from "./roles";

describe("visibleNav (видимость меню по роли)", () => {
  it("кассир видит Сводку, Кассу и Возвраты", () => {
    expect(visibleNav("cashier").map((n) => n.key)).toEqual(["/dashboard", "/pos", "/returns"]);
  });

  it("менеджер видит все разделы", () => {
    expect(visibleNav("manager").length).toBe(6);
  });

  it("владелец видит Товары/Приёмку/Голосовой ввод", () => {
    const keys = visibleNav("owner").map((n) => n.key);
    expect(keys).toContain("/products");
    expect(keys).toContain("/receiving");
    expect(keys).toContain("/voice");
  });

  it("без роли меню пустое", () => {
    expect(visibleNav(null)).toEqual([]);
  });

  it("canAccess: кассир не в manage-ролях", () => {
    expect(canAccess("cashier", ["owner", "manager"])).toBe(false);
    expect(canAccess("manager", ["owner", "manager"])).toBe(true);
  });
});
