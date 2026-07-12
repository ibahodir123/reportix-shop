import { DeleteOutlined, PlusOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Card,
  Col,
  Descriptions,
  Empty,
  Input,
  InputNumber,
  List,
  Modal,
  Radio,
  Row,
  Space,
  Statistic,
  Table,
  Typography,
  message,
} from "antd";
import { useMemo, useState } from "react";

import { api } from "../shared/api";
import type { CartLine, Paginated, Register, Shift, Variant, ZReport } from "../shared/types";

const money = (n: number) => n.toLocaleString("ru-RU") + " сум";

// ──────────────────────────────────────────────────────────────────────────
// Открытие смены
// ──────────────────────────────────────────────────────────────────────────
function OpenShift({ onOpened }: { onOpened: () => void }) {
  const [register, setRegister] = useState<number | null>(null);
  const [openingCash, setOpeningCash] = useState<number>(0);

  const { data: registers } = useQuery({
    queryKey: ["registers"],
    queryFn: async () =>
      (await api.get<Paginated<Register>>("/sales/registers/")).data.results,
  });

  const openMut = useMutation({
    mutationFn: async () =>
      api.post("/sales/shifts/open/", { register, opening_cash: openingCash }),
    onSuccess: () => {
      message.success("Смена открыта");
      onOpened();
    },
    onError: (e: any) =>
      message.error(e?.response?.data?.detail ?? "Не удалось открыть смену"),
  });

  return (
    <Card title="Открыть смену" style={{ maxWidth: 480 }}>
      <Space direction="vertical" style={{ width: "100%" }} size="middle">
        <div>
          <div className="mb-1">Касса</div>
          <Radio.Group
            value={register}
            onChange={(e) => setRegister(e.target.value)}
            options={(registers ?? []).map((r) => ({ label: r.name, value: r.id }))}
          />
          {registers && registers.length === 0 && (
            <Typography.Text type="secondary">
              Нет касс — создайте в админке (/admin).
            </Typography.Text>
          )}
        </div>
        <div>
          <div className="mb-1">Наличные в кассе на начало</div>
          <InputNumber
            min={0}
            value={openingCash}
            onChange={(v) => setOpeningCash(Number(v ?? 0))}
            style={{ width: 200 }}
          />
        </div>
        <Button
          type="primary"
          disabled={!register}
          loading={openMut.isPending}
          onClick={() => openMut.mutate()}
        >
          Открыть смену
        </Button>
      </Space>
    </Card>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Экран продажи
// ──────────────────────────────────────────────────────────────────────────
function SaleScreen({ shift, onClosed }: { shift: Shift; onClosed: () => void }) {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [cart, setCart] = useState<CartLine[]>([]);
  const [discount, setDiscount] = useState(0);
  const [paymentType, setPaymentType] = useState<"cash" | "card" | "mixed">("cash");
  const [paidCash, setPaidCash] = useState(0);
  const [paidCard, setPaidCard] = useState(0);
  const [zReport, setZReport] = useState<ZReport | null>(null);

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

  const subtotal = useMemo(
    () => cart.reduce((s, l) => s + l.quantity * l.price, 0),
    [cart]
  );
  const total = Math.max(0, subtotal - discount);
  const paid = paymentType === "card" ? paidCard : paymentType === "cash" ? paidCash : paidCash + paidCard;
  const change = Math.max(0, paid - total);

  function addVariant(v: Variant) {
    setCart((prev) => {
      const found = prev.find((l) => l.variant.id === v.id);
      if (found) {
        return prev.map((l) =>
          l.variant.id === v.id ? { ...l, quantity: l.quantity + 1 } : l
        );
      }
      return [...prev, { variant: v, quantity: 1, price: Number(v.sale_price) }];
    });
  }

  const saleMut = useMutation({
    mutationFn: async () => {
      const payload = {
        shift: shift.id,
        payment_type: paymentType,
        discount,
        paid_cash: paymentType === "card" ? 0 : paidCash,
        paid_card: paymentType === "cash" ? 0 : paidCard,
        client_uuid: crypto.randomUUID(),
        items: cart.map((l) => ({
          variant: l.variant.id,
          quantity: l.quantity,
          price: l.price,
          discount: 0,
        })),
      };
      return (await api.post("/sales/sales/", payload)).data;
    },
    onSuccess: (sale: any) => {
      message.success(`Чек №${sale.number} проведён. Сдача: ${money(Number(sale.change))}`);
      setCart([]);
      setDiscount(0);
      setPaidCash(0);
      setPaidCard(0);
    },
    onError: (e: any) => {
      const d = e?.response?.data;
      message.error(
        (Array.isArray(d?.detail) ? d.detail.join(", ") : d?.detail) ??
          d?.non_field_errors?.[0] ??
          "Не удалось провести чек"
      );
    },
  });

  const closeMut = useMutation({
    mutationFn: async () =>
      (await api.post<ZReport>(`/sales/shifts/${shift.id}/close/`, {})).data,
    onSuccess: (report) => {
      setZReport(report);
      qc.invalidateQueries({ queryKey: ["current-shift"] });
    },
    onError: () => message.error("Не удалось закрыть смену"),
  });

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          Смена #{shift.id} открыта
        </Typography.Title>
        <Button danger onClick={() => closeMut.mutate()} loading={closeMut.isPending}>
          Закрыть смену
        </Button>
      </Row>

      <Row gutter={16}>
        {/* Поиск товара */}
        <Col xs={24} md={10}>
          <Card title="Товар" size="small">
            <Input.Search
              placeholder="Название, артикул или штрихкод"
              allowClear
              loading={isFetching}
              onChange={(e) => setSearch(e.target.value)}
              autoFocus
            />
            <List
              style={{ marginTop: 12, maxHeight: 420, overflow: "auto" }}
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
                      В чек
                    </Button>,
                  ]}
                >
                  <List.Item.Meta
                    title={v.product_name + (v.name ? ` — ${v.name}` : "")}
                    description={`${v.sku} · ${money(Number(v.sale_price))}`}
                  />
                </List.Item>
              )}
            />
          </Card>
        </Col>

        {/* Чек */}
        <Col xs={24} md={14}>
          <Card title="Чек" size="small">
            {cart.length === 0 ? (
              <Empty description="Чек пуст" />
            ) : (
              <Table
                rowKey={(l) => l.variant.id}
                size="small"
                pagination={false}
                dataSource={cart}
                columns={[
                  {
                    title: "Товар",
                    render: (_, l) => l.variant.product_name + (l.variant.name ? ` — ${l.variant.name}` : ""),
                  },
                  {
                    title: "Кол-во",
                    width: 90,
                    render: (_, l) => (
                      <InputNumber
                        min={1}
                        value={l.quantity}
                        onChange={(v) =>
                          setCart((prev) =>
                            prev.map((x) =>
                              x.variant.id === l.variant.id
                                ? { ...x, quantity: Number(v ?? 1) }
                                : x
                            )
                          )
                        }
                      />
                    ),
                  },
                  { title: "Цена", width: 110, render: (_, l) => money(l.price) },
                  { title: "Сумма", width: 120, render: (_, l) => money(l.quantity * l.price) },
                  {
                    title: "",
                    width: 40,
                    render: (_, l) => (
                      <Button
                        type="text"
                        danger
                        icon={<DeleteOutlined />}
                        onClick={() =>
                          setCart((prev) => prev.filter((x) => x.variant.id !== l.variant.id))
                        }
                      />
                    ),
                  },
                ]}
              />
            )}

            <Row gutter={16} style={{ marginTop: 16 }}>
              <Col span={12}>
                <Space direction="vertical" style={{ width: "100%" }}>
                  <div>
                    Скидка на чек:{" "}
                    <InputNumber
                      min={0}
                      value={discount}
                      onChange={(v) => setDiscount(Number(v ?? 0))}
                    />
                  </div>
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
                  {paymentType !== "card" && (
                    <div>
                      Наличными:{" "}
                      <InputNumber
                        min={0}
                        value={paidCash}
                        onChange={(v) => setPaidCash(Number(v ?? 0))}
                      />
                    </div>
                  )}
                  {paymentType !== "cash" && (
                    <div>
                      Картой:{" "}
                      <InputNumber
                        min={0}
                        value={paidCard}
                        onChange={(v) => setPaidCard(Number(v ?? 0))}
                      />
                    </div>
                  )}
                </Space>
              </Col>
              <Col span={12}>
                <Statistic title="Итого" value={money(total)} />
                <Statistic title="Сдача" value={money(change)} />
                <Button
                  type="primary"
                  size="large"
                  block
                  style={{ marginTop: 12 }}
                  disabled={cart.length === 0 || paid < total}
                  loading={saleMut.isPending}
                  onClick={() => saleMut.mutate()}
                >
                  Провести чек
                </Button>
              </Col>
            </Row>
          </Card>
        </Col>
      </Row>

      <Modal
        open={!!zReport}
        title={`Z-отчёт по смене #${zReport?.shift_id}`}
        onOk={onClosed}
        onCancel={onClosed}
        okText="Готово"
        cancelButtonProps={{ style: { display: "none" } }}
      >
        {zReport && (
          <Descriptions column={1} size="small" bordered>
            <Descriptions.Item label="Чеков">{zReport.sales_count}</Descriptions.Item>
            <Descriptions.Item label="Выручка">{money(Number(zReport.revenue_total))}</Descriptions.Item>
            <Descriptions.Item label="Оплачено картой">{money(Number(zReport.paid_card))}</Descriptions.Item>
            <Descriptions.Item label="Наличных собрано">{money(Number(zReport.cash_collected))}</Descriptions.Item>
            <Descriptions.Item label="Ожидается в кассе">{money(Number(zReport.expected_cash))}</Descriptions.Item>
          </Descriptions>
        )}
      </Modal>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
export function PosPage() {
  const { data, isLoading, refetch } = useQuery({
    queryKey: ["current-shift"],
    queryFn: async () => {
      try {
        return (await api.get<Shift>("/sales/shifts/current/")).data;
      } catch {
        return null;
      }
    },
    retry: false,
  });

  if (isLoading) return null;
  if (!data) return <OpenShift onOpened={() => refetch()} />;
  return <SaleScreen shift={data} onClosed={() => refetch()} />;
}
