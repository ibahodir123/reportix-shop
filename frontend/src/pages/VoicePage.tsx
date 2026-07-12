import { AudioOutlined, LoadingOutlined, SaveOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
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
  Select,
  Space,
  Tag,
  Typography,
  message,
} from "antd";
import { useEffect, useRef, useState } from "react";

import { api } from "../shared/api";
import type { Paginated, Warehouse } from "../shared/types";

export interface Draft {
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

export interface DraftFormValues {
  name: string;
  color: string;
  size: string;
  purchase_price?: number;
  sale_price?: number;
  quantity?: number;
  warehouse?: number;
}

async function parseAudio(blob: Blob, language: string): Promise<ParseResult> {
  const fd = new FormData();
  fd.append("audio", blob, "recording.webm");
  fd.append("language", language);
  return (await api.post<ParseResult>("/voice/parse-product/", fd)).data;
}

async function parseText(text: string, language: string): Promise<ParseResult> {
  return (await api.post<ParseResult>("/voice/parse-product/", { text, language })).data;
}

export function VoicePage() {
  const qc = useQueryClient();
  const [recording, setRecording] = useState(false);
  const [result, setResult] = useState<ParseResult | null>(null);
  const [text, setText] = useState("");
  const [language, setLanguage] = useState("uz-UZ");
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const { data: warehouses } = useQuery({
    queryKey: ["warehouses"],
    queryFn: async () =>
      (await api.get<Paginated<Warehouse>>("/inventory/warehouses/")).data.results,
  });

  const parseMut = useMutation({
    mutationFn: (input: Blob | string) =>
      typeof input === "string"
        ? parseText(input, language)
        : parseAudio(input, language),
    onSuccess: (r) => setResult(r),
    onError: () => message.error("Не удалось распознать/разобрать"),
  });

  const saveMut = useMutation({
    mutationFn: (values: DraftFormValues) =>
      api.post("/catalog/quick-product/", values).then((r) => r.data),
    onSuccess: () => {
      message.success("Товар сохранён");
      setResult(null);
      qc.invalidateQueries({ queryKey: ["products"] });
    },
    onError: (e: any) => {
      const d = e?.response?.data;
      const first =
        d?.detail ??
        (d && typeof d === "object" ? (Object.values(d)[0] as any) : null);
      message.error(
        (Array.isArray(first) ? first[0] : first) ?? "Не удалось сохранить товар"
      );
    },
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
              <Select
                value={language}
                onChange={setLanguage}
                options={[
                  { value: "uz-UZ", label: "O‘zbekcha" },
                  { value: "ru-RU", label: "Русский" },
                ]}
                style={{ width: 180 }}
              />
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

                <DraftForm
                  draft={result.draft}
                  warehouses={warehouses ?? []}
                  saving={saveMut.isPending}
                  onSave={(values) => saveMut.mutate(values)}
                />

                <Alert
                  style={{ marginTop: 12 }}
                  type="info"
                  showIcon
                  message="Проверьте поля и сохраните — товар и приход создаются только по кнопке."
                />
              </>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}

function draftToValues(draft: Draft): DraftFormValues {
  return {
    name: draft.name ?? "",
    color: draft.attributes.color ?? "",
    size: draft.attributes.size ?? "",
    purchase_price: draft.purchase_price ? Number(draft.purchase_price) : undefined,
    sale_price: draft.sale_price ? Number(draft.sale_price) : undefined,
    quantity: draft.quantity ? Number(draft.quantity) : undefined,
    warehouse: undefined,
  };
}

export function DraftForm({
  draft,
  warehouses,
  saving,
  onSave,
}: {
  draft: Draft;
  warehouses: Warehouse[];
  saving: boolean;
  onSave: (values: DraftFormValues) => void;
}) {
  const [values, setValues] = useState<DraftFormValues>(() => draftToValues(draft));

  // Ключевой момент: при каждом НОВОМ результате распознавания форма
  // перезаполняется распознанными значениями (склад сохраняем).
  useEffect(() => {
    setValues((prev) => ({ ...draftToValues(draft), warehouse: prev.warehouse }));
  }, [draft]);

  function set<K extends keyof DraftFormValues>(key: K, value: DraftFormValues[K]) {
    setValues((prev) => ({ ...prev, [key]: value }));
  }

  const needsWarehouse = !!values.quantity && values.quantity > 0 && !values.warehouse;
  const canSave = values.name.trim().length > 0 && !needsWarehouse;

  return (
    <Form layout="vertical">
      <Form.Item label="Наименование">
        <Input
          aria-label="Наименование"
          value={values.name}
          onChange={(e) => set("name", e.target.value)}
        />
      </Form.Item>
      <Row gutter={12}>
        <Col span={12}>
          <Form.Item label="Цвет">
            <Input
              aria-label="Цвет"
              value={values.color}
              onChange={(e) => set("color", e.target.value)}
            />
          </Form.Item>
        </Col>
        <Col span={12}>
          <Form.Item label="Размер">
            <Input
              aria-label="Размер"
              value={values.size}
              onChange={(e) => set("size", e.target.value)}
            />
          </Form.Item>
        </Col>
      </Row>
      <Row gutter={12}>
        <Col span={8}>
          <Form.Item label="Закуп. цена">
            <InputNumber
              aria-label="Закупочная цена"
              style={{ width: "100%" }}
              min={0}
              value={values.purchase_price}
              onChange={(v) => set("purchase_price", v == null ? undefined : Number(v))}
            />
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item label="Цена продажи">
            <InputNumber
              aria-label="Цена продажи"
              style={{ width: "100%" }}
              min={0}
              value={values.sale_price}
              onChange={(v) => set("sale_price", v == null ? undefined : Number(v))}
            />
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item label="Количество">
            <InputNumber
              aria-label="Количество"
              style={{ width: "100%" }}
              min={0}
              value={values.quantity}
              onChange={(v) => set("quantity", v == null ? undefined : Number(v))}
            />
          </Form.Item>
        </Col>
      </Row>
      <Form.Item
        label="Склад (для прихода количества)"
        validateStatus={needsWarehouse ? "error" : undefined}
        help={needsWarehouse ? "Укажите склад для прихода количества" : undefined}
      >
        <Select
          allowClear
          placeholder="Не приходовать"
          value={values.warehouse}
          onChange={(v) => set("warehouse", v ?? undefined)}
          options={warehouses.map((w) => ({ value: w.id, label: w.name }))}
          style={{ maxWidth: 320 }}
        />
      </Form.Item>
      <Button
        type="primary"
        icon={<SaveOutlined />}
        disabled={!canSave}
        loading={saving}
        onClick={() => onSave(values)}
      >
        Сохранить товар
      </Button>
    </Form>
  );
}
