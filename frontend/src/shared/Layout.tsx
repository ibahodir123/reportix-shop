import {
  AppstoreOutlined,
  AudioOutlined,
  DashboardOutlined,
  LogoutOutlined,
  ShopOutlined,
  ShoppingCartOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button, Layout, Menu, Space, Typography } from "antd";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";

import { logout } from "./api";
import { useAuth } from "./auth";

const { Header, Sider, Content } = Layout;

const items = [
  { key: "/dashboard", icon: <DashboardOutlined />, label: <Link to="/dashboard">Сводка</Link> },
  { key: "/pos", icon: <ShoppingCartOutlined />, label: <Link to="/pos">Касса</Link> },
  { key: "/products", icon: <AppstoreOutlined />, label: <Link to="/products">Товары</Link> },
  { key: "/voice", icon: <AudioOutlined />, label: <Link to="/voice">Голосовой ввод</Link> },
];

export function AppLayout() {
  const location = useLocation();
  const selected = "/" + location.pathname.split("/")[1];
  const { user } = useAuth();
  const qc = useQueryClient();
  const nav = useNavigate();

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
