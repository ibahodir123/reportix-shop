import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Col,
  Empty,
  Input,
  InputNumber,
  Radio,
  Row,
  Space,
  Table,
  Typography,
  message,
} from "antd";
import { useState } from "react";

import { api } from "../shared/api";
import { useIdempotencyKey } from "../shared/useIdempotencyKey";

const money = (n: number) => n.toLocaleString("ru-RU") + " сум";

export interface ReturnableItem {
  sale_item: number;
  variant: number;
  variant_name: string;
  price: string;
  sold: string;
  returned: string;
  returnable: string;
}

interface SaleReturnable {
  id: number;
  number: number;
  created_at: string;
  total: string;
  items: ReturnableItem[];
}

export function returnTotal(
  items: ReturnableItem[],
  quantities: Record<number, number>
): number {
  return items.reduce(
    (sum, it) => sum + (quantities[it.sale_item] || 0) * Number(it.price),
    0
  );
}

// Чистая таблица позиций возврата — вынесена для тестируемости.
export function ReturnLinesTable({
  items,
  quantities,
  onQty,
}: {
  items: ReturnableItem[];
  quantities: Record<number, number>;
  onQty: (saleItem: number, value: number) => void;
}) {
  if (items.length === 0) {
    return <Empty description="Найдите чек по номеру" />;
  }
  return (
    <div>
      <Table
        rowKey={(it) => it.sale_item}
        size="small"
        pagination={false}
        dataSource={items}
        columns={[
          { title: "Товар", dataIndex: "variant_name" },
          { title: "Продано", render: (_, it) => it.sold },
          { title: "Возвращено", render: (_, it) => it.returned },
          {
            title: "К возврату",
            width: 130,
            render: (_, it) => (
              <InputNumber
                aria-label={`Возврат ${it.sale_item}`}
                min={0}
                max={Number(it.returnable)}
                value={quantities[it.sale_item] || 0}
                onChange={(v) => onQty(it.sale_item, Number(v ?? 0))}
              />
            ),
          },
          {
            title: "Сумма",
            width: 130,
            render: (_, it) => money((quantities[it.sale_item] || 0) * Number(it.price)),
          },
        ]}
      />
      <Typography.Title level={5} style={{ textAlign: "right", marginTop: 12 }}>
        К возврату: {money(returnTotal(items, quantities))}
      </Typography.Title>
    </div>
  );
}

export function ReturnsPage() {
  const qc = useQueryClient();
  const [number, setNumber] = useState("");
  const [sale, setSale] = useState<SaleReturnable | null>(null);
  const [qtys, setQtys] = useState<Record<number, number>>({});
  const [paymentType, setPaymentType] = useState<"cash" | "card" | "mixed">("cash");
  const [refundCash, setRefundCash] = useState(0);
  const [refundCard, setRefundCard] = useState(0);
  const { key: clientUuid, renew: renewClientUuid } = useIdempotencyKey();

  const { data: shift } = useQuery({
    queryKey: ["current-shift"],
    queryFn: async () => {
      try {
        return (await api.get("/sales/shifts/current/")).data as { id: number };
      } catch {
        return null;
      }
    },
    retry: false,
  });

  const lookupMut = useMutation({
    mutationFn: async (num: string) =>
      (await api.get<SaleReturnable>("/sales/returns/lookup/", { params: { number: num } })).data,
    onSuccess: (s) => {
      setSale(s);
      setQtys({});
    },
    onError: () => {
      setSale(null);
      message.error("Чек не найден");
    },
  });

  const total = sale ? returnTotal(sale.items, qtys) : 0;

  const submitMut = useMutation({
    mutationFn: async () => {
      const items = (sale?.items ?? [])
        .map((it) => ({ sale_item: it.sale_item, quantity: qtys[it.sale_item] || 0 }))
        .filter((l) => l.quantity > 0);
      const payload = {
        sale: sale?.id,
        shift: shift?.id,
        payment_type: paymentType,
        refund_cash: paymentType === "mixed" ? refundCash : 0,
        refund_card: paymentType === "mixed" ? refundCard : 0,
        client_uuid: clientUuid,
        items,
      };
      return (await api.post("/sales/returns/", payload)).data;
    },
    onSuccess: (doc: any) => {
      message.success(`Возврат №${doc.id} проведён на ${money(Number(doc.refund_total))}`);
      setSale(null);
      setQtys({});
      setNumber("");
      renewClientUuid();
      qc.invalidateQueries({ queryKey: ["stocks"] });
    },
    onError: (e: any) => {
      const d = e?.response?.data;
      const first = d?.detail ?? (d && typeof d === "object" ? (Object.values(d)[0] as any) : null);
      message.error((Array.isArray(first) ? first[0] : first) ?? "Не удалось провести возврат");
    },
  });

  const hasLines = sale ? sale.items.some((it) => (qtys[it.sale_item] || 0) > 0) : false;
  const mixedOk = paymentType !== "mixed" || Math.abs(refundCash + refundCard - total) < 0.005;
  const canSubmit = hasLines && mixedOk;

  return (
    <div>
      <Typography.Title level={3}>Возврат товара</Typography.Title>

      <Row gutter={16}>
        <Col xs={24} md={9}>
          <Card title="Чек" size="small">
            <Space direction="vertical" style={{ width: "100%" }} size="middle">
              <Input.Search
                placeholder="Номер чека"
                enterButton="Найти"
                value={number}
                onChange={(e) => setNumber(e.target.value)}
                onSearch={(v) => v.trim() && lookupMut.mutate(v.trim())}
                loading={lookupMut.isPending}
              />
              {sale && (
                <Typography.Text type="secondary">
                  Чек №{sale.number} · сумма {money(Number(sale.total))}
                </Typography.Text>
              )}
            </Space>
          </Card>
        </Col>

        <Col xs={24} md={15}>
          <Card title="Позиции возврата" size="small">
            <ReturnLinesTable
              items={sale?.items ?? []}
              quantities={qtys}
              onQty={(saleItem, v) => setQtys((prev) => ({ ...prev, [saleItem]: v }))}
            />

            {sale && (
              <Space direction="vertical" style={{ width: "100%", marginTop: 16 }}>
                <Radio.Group
                  value={paymentType}
                  onChange={(e) => setPaymentType(e.target.value)}
                  optionType="button"
                  options={[
                    { label: "Наличные", value: "cash" },
                    { label: "Карта", value: "card" },
                    { label: "Смешанная", value: "mixed" },
                  ]}
                />
                {paymentType === "mixed" && (
                  <Space>
                    <span>
                      Наличными:{" "}
                      <InputNumber
                        min={0}
                        value={refundCash}
                        onChange={(v) => setRefundCash(Number(v ?? 0))}
                      />
                    </span>
                    <span>
                      Картой:{" "}
                      <InputNumber
                        min={0}
                        value={refundCard}
                        onChange={(v) => setRefundCard(Number(v ?? 0))}
                      />
                    </span>
                  </Space>
                )}
                {!mixedOk && (
                  <Alert
                    type="warning"
                    showIcon
                    message={`Сумма наличные+карта должна равняться ${money(total)}`}
                  />
                )}
                <Button
                  type="primary"
                  size="large"
                  disabled={!canSubmit || submitMut.isPending}
                  loading={submitMut.isPending}
                  onClick={() => submitMut.mutate()}
                >
                  Провести возврат
                </Button>
              </Space>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}
