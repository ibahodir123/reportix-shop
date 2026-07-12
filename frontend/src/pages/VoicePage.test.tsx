import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DraftForm } from "./VoicePage";
import type { Draft } from "./VoicePage";

afterEach(cleanup);

function makeDraft(over: Partial<Draft>): Draft {
  return {
    name: "Ручка",
    attributes: {},
    purchase_price: "5000",
    sale_price: "9000",
    quantity: "3",
    unit: null,
    confidence: "estimated",
    ...over,
  };
}

describe("DraftForm", () => {
  it("перезаполняет форму при новом результате распознавания", () => {
    const { rerender } = render(
      <DraftForm draft={makeDraft({})} warehouses={[]} saving={false} onSave={vi.fn()} />
    );
    const name = screen.getByLabelText("Наименование") as HTMLInputElement;
    expect(name.value).toBe("Ручка");

    // Повторное распознавание с другими значениями — форма должна обновиться,
    // а не остаться со старыми (баг defaultValue).
    rerender(
      <DraftForm
        draft={makeDraft({ name: "Футболка", attributes: { color: "синий", size: "L" } })}
        warehouses={[]}
        saving={false}
        onSave={vi.fn()}
      />
    );
    expect((screen.getByLabelText("Наименование") as HTMLInputElement).value).toBe(
      "Футболка"
    );
    expect((screen.getByLabelText("Цвет") as HTMLInputElement).value).toBe("синий");
    expect((screen.getByLabelText("Размер") as HTMLInputElement).value).toBe("L");
  });
});
