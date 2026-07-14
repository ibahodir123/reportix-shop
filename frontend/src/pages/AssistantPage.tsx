import {
  AudioOutlined,
  LoadingOutlined,
  RobotOutlined,
  SendOutlined,
} from "@ant-design/icons";
import { useMutation } from "@tanstack/react-query";
import { Button, Card, Input, Select, Space, Typography, message as antdMessage } from "antd";
import { useEffect, useRef, useState } from "react";

import { api } from "../shared/api";

export type ChatState = "collecting" | "confirm" | "done" | "cancelled";

interface AssistantResponse {
  conversation_id: string;
  reply: string;
  state: ChatState;
  draft: unknown;
  result: unknown;
  transcript?: string;
}

export interface ChatMsg {
  role: "user" | "assistant";
  text: string;
}

const GREETING: ChatMsg = {
  role: "assistant",
  text:
    "Здравствуйте! Скажите, что принять на склад. Например: «Прими 20 синих " +
    "футболок размера L по 45 тысяч, продажа 79 тысяч».",
};

export function ChatBubble({ msg }: { msg: ChatMsg }) {
  const mine = msg.role === "user";
  return (
    <div style={{ display: "flex", justifyContent: mine ? "flex-end" : "flex-start" }}>
      <div
        style={{
          maxWidth: "80%",
          margin: "4px 0",
          padding: "8px 12px",
          borderRadius: 12,
          whiteSpace: "pre-wrap",
          background: mine ? "#1677ff" : "#f0f0f0",
          color: mine ? "#fff" : "rgba(0,0,0,0.88)",
        }}
      >
        {msg.text}
      </div>
    </div>
  );
}

export function AssistantPage() {
  const [messages, setMessages] = useState<ChatMsg[]>([GREETING]);
  const [input, setInput] = useState("");
  const [language, setLanguage] = useState("uz-UZ");
  const [lastState, setLastState] = useState<ChatState | null>(null);
  const [recording, setRecording] = useState(false);
  const convIdRef = useRef<string | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const listRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  const sendMut = useMutation({
    mutationFn: async (payload: { text?: string; audio?: Blob }) => {
      if (payload.audio) {
        const fd = new FormData();
        fd.append("audio", payload.audio, "message.webm");
        fd.append("language", language);
        if (convIdRef.current) fd.append("conversation_id", convIdRef.current);
        return (await api.post<AssistantResponse>("/assistant/message/", fd)).data;
      }
      return (
        await api.post<AssistantResponse>("/assistant/message/", {
          conversation_id: convIdRef.current ?? undefined,
          text: payload.text,
        })
      ).data;
    },
    onSuccess: (data) => {
      setMessages((m) => {
        const next = [...m];
        // Голос: показываем распознанный текст — видно, что расслышал Google.
        if (data.transcript) {
          next.push({ role: "user", text: "🎤 " + data.transcript });
        }
        next.push({ role: "assistant", text: data.reply });
        return next;
      });
      setLastState(data.state);
      // После завершения/отмены — начинаем новый диалог со следующего сообщения.
      convIdRef.current =
        data.state === "done" || data.state === "cancelled" ? null : data.conversation_id;
    },
    onError: () => antdMessage.error("Не удалось связаться с помощником"),
  });

  function sendText(raw: string) {
    const t = raw.trim();
    if (!t || sendMut.isPending) return;
    setMessages((m) => [...m, { role: "user", text: t }]);
    sendMut.mutate({ text: t });
  }

  function onSend() {
    sendText(input);
    setInput("");
  }

  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (e) => e.data.size > 0 && chunksRef.current.push(e.data);
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        stream.getTracks().forEach((t) => t.stop());
        // Пузырь с распознанным текстом добавится в onSuccess (из ответа).
        sendMut.mutate({ audio: blob });
      };
      recorder.start();
      recorderRef.current = recorder;
      setRecording(true);
    } catch {
      antdMessage.error("Нет доступа к микрофону");
    }
  }

  function stopRecording() {
    recorderRef.current?.stop();
    setRecording(false);
  }

  const confirming = lastState === "confirm";

  return (
    <div>
      <Typography.Title level={3}>
        <RobotOutlined /> Помощник
      </Typography.Title>
      <Typography.Paragraph type="secondary">
        Напишите или продиктуйте, что принять на склад. Помощник переспросит, что
        нужно, покажет итог — и создаст товар только после вашего «Подтверждаю».
      </Typography.Paragraph>

      <Card size="small" style={{ maxWidth: 720 }}>
        <div
          ref={listRef}
          style={{ height: 380, overflowY: "auto", padding: "4px 4px 8px" }}
        >
          {messages.map((m, i) => (
            <ChatBubble key={i} msg={m} />
          ))}
          {sendMut.isPending && (
            <div style={{ color: "rgba(0,0,0,0.45)", padding: "4px 4px" }}>
              <LoadingOutlined /> помощник печатает…
            </div>
          )}
        </div>

        {confirming && (
          <Space style={{ marginBottom: 8 }}>
            <Button
              type="primary"
              onClick={() => sendText("Подтверждаю")}
              disabled={sendMut.isPending}
            >
              Подтверждаю
            </Button>
            <Button onClick={() => sendText("Отмена")} disabled={sendMut.isPending}>
              Отмена
            </Button>
          </Space>
        )}

        <Space.Compact style={{ width: "100%" }}>
          <Select
            value={language}
            onChange={setLanguage}
            options={[
              { value: "uz-UZ", label: "UZ" },
              { value: "ru-RU", label: "RU" },
            ]}
            style={{ width: 80 }}
          />
          <Input
            aria-label="Сообщение помощнику"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onPressEnter={onSend}
            placeholder="Напишите сообщение…"
            disabled={sendMut.isPending}
          />
          <Button
            icon={recording ? <LoadingOutlined /> : <AudioOutlined />}
            danger={recording}
            onClick={recording ? stopRecording : startRecording}
            title={recording ? "Остановить запись" : "Записать голос"}
          />
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={onSend}
            loading={sendMut.isPending}
            disabled={!input.trim()}
          >
            Отправить
          </Button>
        </Space.Compact>
      </Card>
    </div>
  );
}
