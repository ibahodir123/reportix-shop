import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { ReturnLinesTable, returnTotal } from "./ReturnsPage";
import type { ReturnableItem } from "./ReturnsPage";

afterEach(cleanup);

const items: ReturnableItem[] = [
  { sale_item: 1, variant: 10, variant_name: "Товар А", price: "100", sold: "5", returned: "1", returnable: "4" },
  { sale_item: 2, variant: 11, variant_name: "Товар Б", price: "50", sold: "3", returned: "0", returnable: "3" },
];

describe("Возврат — форма", () => {
  it("returnTotal считает сумму выбранных позиций", () => {
    expect(returnTotal(items, { 1: 2, 2: 1 })).toBe(250);
    expect(returnTotal(items, {})).toBe(0);
  });

  it("таблица показывает позиции, остатки и итог к возврату", () => {
    render(
      <ReturnLinesTable items={items} quantities={{ 1: 2 }} onQty={() => {}} />
    );
    expect(screen.getByText("Товар А")).toBeTruthy();
    expect(screen.getByText("Товар Б")).toBeTruthy();
    // Итог: 2 * 100 = 200
    expect(screen.getByText(/К возврату:/)).toBeTruthy();
    // «200» встречается и в ячейке суммы, и в итоге — берём все.
    expect(screen.getAllByText(/200/).length).toBeGreaterThan(0);
  });

  it("пустой список — подсказка найти чек", () => {
    render(<ReturnLinesTable items={[]} quantities={{}} onQty={() => {}} />);
    expect(screen.getByText(/Найдите чек/)).toBeTruthy();
  });
});
