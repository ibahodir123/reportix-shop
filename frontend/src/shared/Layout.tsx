import {
  AppstoreOutlined,
  AudioOutlined,
  DashboardOutlined,
  ImportOutlined,
  LogoutOutlined,
  RollbackOutlined,
  ShopOutlined,
  ShoppingCartOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button, Layout, Menu, Space, Typography } from "antd";
import type { ReactNode } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";

import { logout } from "./api";
import { useAuth } from "./auth";
import { visibleNav } from "./roles";

const { Header, Sider, Content } = Layout;

const ICONS: Record<string, ReactNode> = {
  "/dashboard": <DashboardOutlined />,
  "/pos": <ShoppingCartOutlined />,
  "/returns": <RollbackOutlined />,
  "/receiving": <ImportOutlined />,
  "/products": <AppstoreOutlined />,
  "/voice": <AudioOutlined />,
};

export function AppLayout() {
  const location = useLocation();
  const selected = "/" + location.pathname.split("/")[1];
  const { user } = useAuth();
  const qc = useQueryClient();
  const nav = useNavigate();

  // Меню по роли (backend всё равно защищает эндпоинты).
  const items = visibleNav(user?.role ?? null).map((entry) => ({
    key: entry.key,
    icon: ICONS[entry.key],
    label: <Link to={entry.key}>{entry.label}</Link>,
  }));

  const logoutMut = useMutation({
    mutationFn: logout,
    onSuccess: () => {
      qc.setQueryData(["me"], null);
      qc.clear();
      nav("/login", { replace: true });
    },
  });

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider theme="light" breakpoint="lg" collapsedWidth="0">
        <div className="flex items-center gap-2 px-4 py-4 text-lg font-bold">
          <ShopOutlined /> REPORTIX
        </div>
        <Menu mode="inline" selectedKeys={[selected]} items={items} />
      </Sider>
      <Layout>
        <Header
          style={{
            background: "#fff",
            paddingInline: 24,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <span className="text-base font-medium">Розничная торговля</span>
          <Space>
            {user && (
              <Typography.Text type="secondary">
                <UserOutlined /> {user.username}
                {user.current_tenant ? ` · ${user.current_tenant.name}` : ""}
              </Typography.Text>
            )}
            <Button
              icon={<LogoutOutlined />}
              onClick={() => logoutMut.mutate()}
              loading={logoutMut.isPending}
            >
              Выйти
            </Button>
          </Space>
        </Header>
        <Content style={{ margin: 24 }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
