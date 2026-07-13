import { act, cleanup, fireEvent, render, renderHook, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { useIdempotencyKey } from "./useIdempotencyKey";

afterEach(cleanup);

describe("useIdempotencyKey", () => {
  it("ключ стабилен между рендерами (повторная отправка использует тот же UUID)", () => {
    const { result, rerender } = renderHook(() => useIdempotencyKey());
    const first = result.current.key;
    rerender();
    rerender();
    expect(result.current.key).toBe(first);
  });

  it("renew() выдаёт новый UUID (после успеха/сброса)", () => {
    const { result } = renderHook(() => useIdempotencyKey());
    const first = result.current.key;
    act(() => result.current.renew());
    expect(result.current.key).not.toBe(first);
  });
});

// Имитация сценария страницы: submit фиксирует текущий ключ, success — renew.
function Harness({ onSubmit }: { onSubmit: (key: string) => void }) {
  const { key, renew } = useIdempotencyKey();
  return (
    <>
      <button onClick={() => onSubmit(key)}>submit</button>
      <button onClick={() => renew()}>success</button>
    </>
  );
}

describe("сценарий документа/чека", () => {
  it("повторная отправка — тот же UUID; после успеха — новый", () => {
    const keys: string[] = [];
    render(<Harness onSubmit={(k) => keys.push(k)} />);

    fireEvent.click(screen.getByText("submit")); // первая отправка
    fireEvent.click(screen.getByText("submit")); // повтор/retry
    expect(keys[0]).toBe(keys[1]);

    fireEvent.click(screen.getByText("success")); // успех → renew
    fireEvent.click(screen.getByText("submit")); // новый документ
    expect(keys[2]).not.toBe(keys[0]);
  });
});
