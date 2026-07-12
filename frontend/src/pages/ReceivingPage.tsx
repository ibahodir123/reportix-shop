import { DeleteOutlined, PlusOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Card,
  Col,
  Empty,
  Input,
  InputNumber,
  List,
  Row,
  Select,
  Space,
  Table,
  Typography,
  message,
} from "antd";
import { useState } from "react";

import { api } from "../shared/api";
import type { Paginated, Variant, Warehouse } from "../shared/types";
import { createClientUuid } from "../shared/uuid";

const money = (n: number) => n.toLocaleString("ru-RU") + " сум";

export interface ReceiptLine {
  variant: Variant;
  quantity: number;
  purchase_price: number;
}

export function receiptTotal(lines: ReceiptLine[]): number {
  return lines.reduce((sum, l) => sum + (l.quantity || 0) * (l.purchase_price || 0), 0);
}

// Чистая таблица позиций документа — вынесена для тестируемости.
export function ReceiptLinesTable({
  lines,
  onQty,
  onPrice,
  onRemove,
}: {
  lines: ReceiptLine[];
  onQty: (index: number, value: number) => void;
  onPrice: (index: number, value: number) => void;
  onRemove: (index: number) => void;
}) {
  if (lines.length === 0) {
    return <Empty description="Добавьте позиции" />;
  }
  return (
    <div>
      <Table
        rowKey={(l) => l.variant.id}
        size="small"
        pagination={false}
        dataSource={lines}
        columns={[
          {
            title: "Товар",
            render: (_, l) =>
              l.variant.product_name + (l.variant.name ? ` — ${l.variant.name}` : ""),
          },
          {
            title: "Кол-во",
            width: 110,
            render: (_, l, i) => (
              <InputNumber
                aria-label="Количество"
                min={0}
                value={l.quantity}
                onChange={(v) => onQty(i, Number(v ?? 0))}
              />
            ),
          },
          {
            title: "Закуп. цена",
            width: 130,
            render: (_, l, i) => (
              <InputNumber
                aria-label="Цена"
                min={0}
                value={l.purchase_price}
                onChange={(v) => onPrice(i, Number(v ?? 0))}
              />
            ),
          },
          {
            title: "Сумма",
            width: 130,
            render: (_, l) => money(l.quantity * l.purchase_price),
          },
          {
            title: "",
            width: 40,
            render: (_, __, i) => (
              <Button
                type="text"
                danger
                aria-label="Удалить строку"
                icon={<DeleteOutlined />}
                onClick={() => onRemove(i)}
              />
            ),
          },
        ]}
      />
      <Typography.Title level={5} style={{ textAlign: "right", marginTop: 12 }}>
        Итого: {money(receiptTotal(lines))}
      </Typography.Title>
    </div>
  );
}

export function ReceivingPage() {
  const qc = useQueryClient();
  const [warehouse, setWarehouse] = useState<number | undefined>(undefined);
  const [search, setSearch] = useState("");
  const [lines, setLines] = useState<ReceiptLine[]>([]);

  const { data: warehouses } = useQuery({
    queryKey: ["warehouses"],
    queryFn: async () =>
      (await api.get<Paginated<Warehouse>>("/inventory/warehouses/")).data.results,
  });

  const { data: results, isFetching } = useQuery({
    queryKey: ["variant-search", search],
    queryFn: async () =>
      (
        await api.get<Paginated<Variant>>("/catalog/variants/", {
          params: { search, active: 1 },
        })
      ).data.results,
    enabled: search.length > 0,
  });

  function addVariant(v: Variant) {
    setLines((prev) => {
      const idx = prev.findIndex((l) => l.variant.id === v.id);
      if (idx >= 0) {
        return prev.map((l, i) => (i === idx ? { ...l, quantity: l.quantity + 1 } : l));
      }
      return [...prev, { variant: v, quantity: 1, purchase_price: Number(v.purchase_price) }];
    });
  }

  const submitMut = useMutation({
    mutationFn: async () => {
      const payload = {
        warehouse,
        client_uuid: createClientUuid(),
        items: lines.map((l) => ({
          variant: l.variant.id,
          quantity: l.quantity,
          purchase_price: l.purchase_price,
        })),
      };
      return (await api.post("/inventory/receipts/", payload)).data;
    },
    onSuccess: (receipt: any) => {
      message.success(`Приёмка №${receipt.id} проведена на ${money(Number(receipt.total_cost))}`);
      setLines([]);
      setSearch("");
      qc.invalidateQueries({ queryKey: ["stocks"] });
    },
    onError: (e: any) => {
      const d = e?.response?.data;
      const first =
        d?.detail ?? (d && typeof d === "object" ? (Object.values(d)[0] as any) : null);
      message.error(
        (Array.isArray(first) ? first[0] : first) ?? "Не удалось провести приёмку"
      );
    },
  });

  const hasBadQty = lines.some((l) => l.quantity <= 0);
  const canSubmit = !!warehouse && lines.length > 0 && !hasBadQty;

  return (
    <div>
      <Typography.Title level={3}>Приёмка товара</Typography.Title>

      <Row gutter={16}>
        <Col xs={24} md={9}>
          <Card title="Товар" size="small">
            <Space direction="vertical" style={{ width: "100%" }} size="middle">
              <Select
                placeholder="Склад приёмки"
                value={warehouse}
                onChange={setWarehouse}
                options={(warehouses ?? []).map((w) => ({ value: w.id, label: w.name }))}
                style={{ width: "100%" }}
              />
              <Input.Search
                placeholder="Название, артикул или штрихкод"
                allowClear
                loading={isFetching}
                onChange={(e) => setSearch(e.target.value)}
              />
              <List
                style={{ maxHeight: 380, overflow: "auto" }}
                dataSource={results ?? []}
                locale={{ emptyText: search ? "Ничего не найдено" : "Начните вводить запрос" }}
                renderItem={(v) => (
                  <List.Item
                    actions={[
                      <Button
                        key="add"
                        type="link"
                        icon={<PlusOutlined />}
                        onClick={() => addVariant(v)}
                      >
                        Добавить
                      </Button>,
                    ]}
                  >
                    <List.Item.Meta
                      title={v.product_name + (v.name ? ` — ${v.name}` : "")}
                      description={v.sku}
                    />
                  </List.Item>
                )}
              />
            </Space>
          </Card>
        </Col>

        <Col xs={24} md={15}>
          <Card title="Документ приёмки" size="small">
            <ReceiptLinesTable
              lines={lines}
              onQty={(i, v) =>
                setLines((prev) => prev.map((l, idx) => (idx === i ? { ...l, quantity: v } : l)))
              }
              onPrice={(i, v) =>
                setLines((prev) =>
                  prev.map((l, idx) => (idx === i ? { ...l, purchase_price: v } : l))
                )
              }
              onRemove={(i) => setLines((prev) => prev.filter((_, idx) => idx !== i))}
            />
            <Button
              type="primary"
              size="large"
              style={{ marginTop: 16 }}
              disabled={!canSubmit}
              loading={submitMut.isPending}
              onClick={() => submitMut.mutate()}
            >
              Провести приёмку
            </Button>
            {!warehouse && lines.length > 0 && (
              <Typography.Text type="warning" style={{ marginLeft: 12 }}>
                Выберите склад
              </Typography.Text>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}
