import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ReceiptLinesTable, receiptTotal } from "./ReceivingPage";
import type { ReceiptLine } from "./ReceivingPage";
import type { Variant } from "../shared/types";

afterEach(cleanup);

function variant(id: number, name: string, price: string): Variant {
  return {
    id,
    product: 1,
    product_name: name,
    sku: `SKU-${id}`,
    name: "",
    attributes: {},
    purchase_price: price,
    sale_price: price,
    is_active: true,
    barcodes: [],
  };
}

const lines: ReceiptLine[] = [
  { variant: variant(1, "Товар А", "100"), quantity: 2, purchase_price: 100 },
  { variant: variant(2, "Товар Б", "50"), quantity: 3, purchase_price: 50 },
];

describe("Приёмка — документ", () => {
  it("считает итог по позициям", () => {
    expect(receiptTotal(lines)).toBe(350);
  });

  it("показывает позиции и итог, удаление строки вызывает колбэк", () => {
    const onRemove = vi.fn();
    render(
      <ReceiptLinesTable
        lines={lines}
        onQty={vi.fn()}
        onPrice={vi.fn()}
        onRemove={onRemove}
      />
    );

    expect(screen.getByText("Товар А")).toBeTruthy();
    expect(screen.getByText("Товар Б")).toBeTruthy();
    expect(screen.getByText(/Итого:/)).toBeTruthy();
    expect(screen.getByText(/350/)).toBeTruthy();

    const removeButtons = screen.getAllByLabelText("Удалить строку");
    expect(removeButtons.length).toBe(2);
    fireEvent.click(removeButtons[0]);
    expect(onRemove).toHaveBeenCalledWith(0);
  });
});
