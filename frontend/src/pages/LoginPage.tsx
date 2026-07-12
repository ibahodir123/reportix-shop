import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button, Card, Form, Input, Typography, message } from "antd";
import { Navigate, useNavigate } from "react-router-dom";

import { login } from "../shared/api";
import { useAuth } from "../shared/auth";
import type { CurrentUser } from "../shared/types";

export function LoginPage() {
  const qc = useQueryClient();
  const nav = useNavigate();
  const { user, isLoading } = useAuth();

  const loginMut = useMutation({
    mutationFn: (v: { username: string; password: string }) => login(v.username, v.password),
    onSuccess: (me: CurrentUser) => {
      qc.setQueryData(["me"], me);
      nav("/dashboard", { replace: true });
    },
    onError: (e: any) =>
      message.error(e?.response?.data?.detail ?? "Не удалось войти"),
  });

  // Уже авторизован — на дашборд.
  if (!isLoading && user) {
    return <Navigate to="/dashboard" replace />;
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "#f5f5f5",
      }}
    >
      <Card style={{ width: 360 }}>
        <Typography.Title level={3} style={{ textAlign: "center", marginBottom: 24 }}>
          REPORTIX
        </Typography.Title>
        <Form layout="vertical" onFinish={(v) => loginMut.mutate(v)}>
          <Form.Item
            name="username"
            label="Логин"
            rules={[{ required: true, message: "Введите логин" }]}
          >
            <Input autoFocus autoComplete="username" />
          </Form.Item>
          <Form.Item
            name="password"
            label="Пароль"
            rules={[{ required: true, message: "Введите пароль" }]}
          >
            <Input.Password autoComplete="current-password" />
          </Form.Item>
          <Button type="primary" htmlType="submit" block loading={loginMut.isPending}>
            Войти
          </Button>
        </Form>
      </Card>
    </div>
  );
}
