import { useQuery } from "@tanstack/react-query";
import { Alert, Input, Table, Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useState } from "react";

import { api } from "../shared/api";
import type { Paginated, Product } from "../shared/types";

async function fetchProducts(search: string): Promise<Paginated<Product>> {
  const { data } = await api.get<Paginated<Product>>("/catalog/products/", {
    params: search ? { search } : undefined,
  });
  return data;
}

const columns: ColumnsType<Product> = [
  { title: "Наименование", dataIndex: "name", key: "name" },
  {
    title: "Вариантов",
    key: "variants",
    render: (_, p) => p.variants.length,
  },
  {
    title: "Цена (от)",
    key: "price",
    render: (_, p) => {
      const prices = p.variants.map((v) => Number(v.sale_price));
      return prices.length ? Math.min(...prices).toLocaleString("ru-RU") + " сум" : "—";
    },
  },
  {
    title: "Статус",
    dataIndex: "is_active",
    key: "is_active",
    render: (active: boolean) =>
      active ? <Tag color="green">Активен</Tag> : <Tag>Скрыт</Tag>,
  },
];

export function ProductsPage() {
  const [search, setSearch] = useState("");
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["products", search],
    queryFn: () => fetchProducts(search),
  });

  return (
    <div>
      <Typography.Title level={3}>Товары</Typography.Title>
      <Input.Search
        placeholder="Поиск по наименованию"
        allowClear
        onSearch={setSearch}
        style={{ maxWidth: 360, marginBottom: 16 }}
      />
      {isError && (
        <Alert
          type="error"
          showIcon
          message="Не удалось загрузить товары"
          description={(error as Error)?.message}
          style={{ marginBottom: 16 }}
        />
      )}
      <Table
        rowKey="id"
        loading={isLoading}
        columns={columns}
        dataSource={data?.results ?? []}
        pagination={{ total: data?.count ?? 0, pageSize: 50 }}
      />
    </div>
  );
}
