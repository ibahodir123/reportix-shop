import {
  AppstoreOutlined,
  AudioOutlined,
  DashboardOutlined,
  ShopOutlined,
  ShoppingCartOutlined,
} from "@ant-design/icons";
import { Layout, Menu } from "antd";
import { Link, Outlet, useLocation } from "react-router-dom";

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

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider theme="light" breakpoint="lg" collapsedWidth="0">
        <div className="flex items-center gap-2 px-4 py-4 text-lg font-bold">
          <ShopOutlined /> REPORTIX
        </div>
        <Menu mode="inline" selectedKeys={[selected]} items={items} />
      </Sider>
      <Layout>
        <Header style={{ background: "#fff", paddingInline: 24 }}>
          <span className="text-base font-medium">Розничная торговля</span>
        </Header>
        <Content style={{ margin: 24 }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
