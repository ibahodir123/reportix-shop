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
