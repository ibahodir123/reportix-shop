export interface Barcode {
  id: number;
  code: string;
}

export interface Variant {
  id: number;
  product: number;
  product_name: string;
  sku: string;
  name: string;
  attributes: Record<string, string>;
  purchase_price: string;
  sale_price: string;
  is_active: boolean;
  barcodes: Barcode[];
}

export interface Product {
  id: number;
  name: string;
  category: number | null;
  brand: number | null;
  unit: number;
  description: string | null;
  is_active: boolean;
  variants: Variant[];
  created_at: string;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface Warehouse {
  id: number;
  branch: number;
  name: string;
  is_active: boolean;
}

export interface Register {
  id: number;
  branch: number;
  warehouse: number;
  name: string;
  is_active: boolean;
}

export interface Shift {
  id: number;
  register: number;
  cashier: number;
  cashier_name: string;
  status: string;
  opened_at: string;
  closed_at: string | null;
  opening_cash: string;
  closing_cash: string | null;
}

export interface ZReport {
  shift_id: number;
  sales_count: number;
  revenue_total: string;
  paid_card: string;
  cash_collected: string;
  opening_cash: string;
  expected_cash: string;
  closing_cash: string | null;
}

export interface CartLine {
  variant: Variant;
  quantity: number;
  price: number;
}

export interface Membership {
  tenant_id: number;
  tenant_name: string;
  role: string;
  branch: number | null;
}

export type Role = "owner" | "manager" | "cashier";

export interface CurrentUser {
  id: number;
  username: string;
  phone: string | null;
  is_staff: boolean;
  role: Role | null;
  branch: number | null;
  current_tenant: { id: number; name: string } | null;
  memberships: Membership[];
}
