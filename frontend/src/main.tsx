import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ConfigProvider, Spin } from "antd";
import ruRU from "antd/locale/ru_RU";
import React from "react";
import ReactDOM from "react-dom/client";
import { RouterProvider, createBrowserRouter, Navigate } from "react-router-dom";

import "antd/dist/reset.css";
import "./index.css";

import { AppLayout } from "./shared/Layout";
import { RequireRole } from "./shared/RequireRole";
import { useAuth } from "./shared/auth";
import { MANAGE_ROLES } from "./shared/roles";
import { AssistantPage } from "./pages/AssistantPage";
import { DashboardPage } from "./pages/DashboardPage";
import { LoginPage } from "./pages/LoginPage";
import { PosPage } from "./pages/PosPage";
import { ProductsPage } from "./pages/ProductsPage";
import { ReceivingPage } from "./pages/ReceivingPage";
import { ReturnsPage } from "./pages/ReturnsPage";
import { VoicePage } from "./pages/VoicePage";

const queryClient = new QueryClient();

// Пускает внутрь только авторизованных; иначе — на /login.
function RequireAuth() {
  const { user, isLoading } = useAuth();
  if (isLoading) {
    return (
      <div style={{ minHeight: "100vh", display: "grid", placeItems: "center" }}>
        <Spin size="large" />
      </div>
    );
  }
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  return <AppLayout />;
}

const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  {
    path: "/",
    element: <RequireAuth />,
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      { path: "dashboard", element: <DashboardPage /> },
      { path: "pos", element: <PosPage /> },
      { path: "returns", element: <ReturnsPage /> },
      {
        path: "receiving",
        element: (
          <RequireRole roles={MANAGE_ROLES}>
            <ReceivingPage />
          </RequireRole>
        ),
      },
      {
        path: "products",
        element: (
          <RequireRole roles={MANAGE_ROLES}>
            <ProductsPage />
          </RequireRole>
        ),
      },
      {
        path: "voice",
        element: (
          <RequireRole roles={MANAGE_ROLES}>
            <VoicePage />
          </RequireRole>
        ),
      },
      {
        path: "assistant",
        element: (
          <RequireRole roles={MANAGE_ROLES}>
            <AssistantPage />
          </RequireRole>
        ),
      },
    ],
  },
]);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ConfigProvider locale={ruRU}>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </ConfigProvider>
  </React.StrictMode>
);
