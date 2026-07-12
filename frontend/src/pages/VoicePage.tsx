import { AudioOutlined, LoadingOutlined } from "@ant-design/icons";
import { useMutation } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Form,
  Input,
  InputNumber,
  Row,
  Space,
  Tag,
  Typography,
  message,
} from "antd";
import { useRef, useState } from "react";

import { api } from "../shared/api";

interface Draft {
  name: string | null;
  attributes: { color?: string; size?: string };
  purchase_price: string | null;
  sale_price: string | null;
  quantity: string | null;
  unit: string | null;
  confidence: string;
}

interface ParseResult {
  provider: string;
  transcript: string;
  draft: Draft;
}

async function parseAudio(blob: Blob): Promise<ParseResult> {
  const fd = new FormData();
  fd.append("audio", blob, "recording.webm");
  return (await api.post<ParseResult>("/voice/parse-product/", fd)).data;
}

async function parseText(text: string): Promise<ParseResult> {
  return (await api.post<ParseResult>("/voice/parse-product/", { text })).data;
}

export function VoicePage() {
  const [recording, setRecording] = useState(false);
  const [result, setResult] = useState<ParseResult | null>(null);
  const [text, setText] = useState("");
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const parseMut = useMutation({
    mutationFn: (input: Blob | string) =>
      typeof input === "string" ? parseText(input) : parseAudio(input),
    onSuccess: (r) => setResult(r),
    onError: () => message.error("Не удалось распознать/разобрать"),
  });

  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (e) => e.data.size > 0 && chunksRef.current.push(e.data);
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        stream.getTracks().forEach((t) => t.stop());
        parseMut.mutate(blob);
      };
      recorder.start();
      recorderRef.current = recorder;
      setRecording(true);
    } catch {
      message.error("Нет доступа к микрофону");
    }
  }

  function stopRecording() {
    recorderRef.current?.stop();
    setRecording(false);
  }

  return (
    <div>
      <Typography.Title level={3}>Голосовой ввод товара</Typography.Title>
      <Typography.Paragraph type="secondary">
        Продиктуйте наименование и цифры, например: «Футболка синяя размер эль
        закуп 45 тысяч продажа 79 тысяч 20 штук». Система заполнит черновик —
        проверьте и сохраните.
      </Typography.Paragraph>

      <Row gutter={16}>
        <Col xs={24} md={10}>
          <Card title="Запись" size="small">
            <Space direction="vertical" style={{ width: "100%" }} size="middle">
              <Button
                type={recording ? "default" : "primary"}
                danger={recording}
                size="large"
                icon={parseMut.isPending ? <LoadingOutlined /> : <AudioOutlined />}
                onClick={recording ? stopRecording : startRecording}
                loading={parseMut.isPending && !recording}
                block
              >
                {recording ? "Остановить запись" : "Записать голос"}
              </Button>

              <Typography.Text type="secondary">или введите текстом:</Typography.Text>
              <Input.TextArea
                rows={3}
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Футболка синяя размер эль закуп 45 тысяч продажа 79 тысяч 20 штук"
              />
              <Button
                onClick={() => parseMut.mutate(text)}
                disabled={!text.trim()}
                loading={parseMut.isPending}
              >
                Разобрать текст
              </Button>
            </Space>
          </Card>
        </Col>

        <Col xs={24} md={14}>
          <Card title="Черновик товара" size="small">
            {!result ? (
              <Typography.Text type="secondary">
                Здесь появится распознанный товар.
              </Typography.Text>
            ) : (
              <>
                <Descriptions size="small" column={1} style={{ marginBottom: 16 }}>
                  <Descriptions.Item label="Распознано">
                    «{result.transcript}»{" "}
                    <Tag>{result.provider}</Tag>
                    <Tag color="orange">черновик · {result.draft.confidence}</Tag>
                  </Descriptions.Item>
                </Descriptions>

                <DraftForm draft={result.draft} />

                <Alert
                  style={{ marginTop: 12 }}
                  type="info"
                  showIcon
                  message="Распознавание не пишет в базу — проверьте поля и сохраните вручную."
                />
              </>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}

function DraftForm({ draft }: { draft: Draft }) {
  return (
    <Form layout="vertical">
      <Form.Item label="Наименование">
        <Input defaultValue={draft.name ?? ""} />
      </Form.Item>
      <Row gutter={12}>
        <Col span={12}>
          <Form.Item label="Цвет">
            <Input defaultValue={draft.attributes.color ?? ""} />
          </Form.Item>
        </Col>
        <Col span={12}>
          <Form.Item label="Размер">
            <Input defaultValue={draft.attributes.size ?? ""} />
          </Form.Item>
        </Col>
      </Row>
      <Row gutter={12}>
        <Col span={8}>
          <Form.Item label="Закуп. цена">
            <InputNumber
              style={{ width: "100%" }}
              defaultValue={draft.purchase_price ? Number(draft.purchase_price) : undefined}
            />
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item label="Цена продажи">
            <InputNumber
              style={{ width: "100%" }}
              defaultValue={draft.sale_price ? Number(draft.sale_price) : undefined}
            />
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item label="Количество">
            <InputNumber
              style={{ width: "100%" }}
              defaultValue={draft.quantity ? Number(draft.quantity) : undefined}
            />
          </Form.Item>
        </Col>
      </Row>
    </Form>
  );
}
