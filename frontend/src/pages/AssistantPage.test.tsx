import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AssistantPage, ChatBubble } from "./AssistantPage";
import { api } from "../shared/api";

afterEach(cleanup);

function wrap(node: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{node}</QueryClientProvider>;
}

describe("ChatBubble", () => {
  it("показывает текст сообщения", () => {
    render(<ChatBubble msg={{ role: "assistant", text: "Привет" }} />);
    expect(screen.getByText("Привет")).toBeTruthy();
  });
});

describe("AssistantPage", () => {
  it("отправляет сообщение и показывает ответ помощника", async () => {
    const post = vi.spyOn(api, "post").mockResolvedValue({
      data: {
        conversation_id: "abc",
        reply: "На склад «Основной»?",
        state: "collecting",
        draft: null,
        result: null,
      },
    } as never);

    render(wrap(<AssistantPage />));

    const input = screen.getByLabelText("Сообщение помощнику");
    fireEvent.change(input, { target: { value: "Прими 20 футболок" } });
    fireEvent.click(screen.getByText("Отправить"));

    // Сообщение пользователя видно сразу.
    expect(screen.getByText("Прими 20 футболок")).toBeTruthy();
    // Ответ помощника приходит из мока.
    await waitFor(() => expect(screen.getByText("На склад «Основной»?")).toBeTruthy());

    expect(post).toHaveBeenCalledWith("/assistant/message/", {
      conversation_id: undefined,
      text: "Прими 20 футболок",
    });
  });

  it("показывает кнопку «Подтверждаю» на шаге подтверждения", async () => {
    vi.spyOn(api, "post").mockResolvedValue({
      data: {
        conversation_id: "abc",
        reply: "Создать товар «Футболка»?",
        state: "confirm",
        draft: { intent: "intake" },
        result: null,
      },
    } as never);

    render(wrap(<AssistantPage />));
    fireEvent.change(screen.getByLabelText("Сообщение помощнику"), {
      target: { value: "Прими 20 футболок на основной склад" },
    });
    fireEvent.click(screen.getByText("Отправить"));

    await waitFor(() => expect(screen.getByText("Подтверждаю")).toBeTruthy());
  });
});
