-- Schema inferido a partir dos arquivos CSV.
-- Revisar os tipos com o dicionário de dados do ERP antes de produção.

BEGIN;

CREATE TABLE "addresses" (
    "id" INTEGER,
    "customer_id" INTEGER,
    "address_type" TEXT,
    "postal_code" TEXT,
    "street" TEXT,
    "number" TEXT,
    "complement" TEXT,
    "district" TEXT,
    "city" TEXT,
    "state" TEXT,
    "country" TEXT,
    "is_primary" BOOLEAN
);

CREATE TABLE "attributes" (
    "id" INTEGER,
    "name" TEXT,
    "data_type" TEXT
);

CREATE TABLE "brands" (
    "id" INTEGER,
    "name" TEXT,
    "country" TEXT,
    "is_active" BOOLEAN,
    "created_at" TIMESTAMP WITHOUT TIME ZONE,
    "updated_at" TIMESTAMP WITHOUT TIME ZONE
);

CREATE TABLE "categories" (
    "id" INTEGER,
    "name" TEXT,
    "slug" TEXT,
    "parent_category_id" INTEGER,
    "is_active" BOOLEAN,
    "created_at" TIMESTAMP WITHOUT TIME ZONE,
    "updated_at" TIMESTAMP WITHOUT TIME ZONE
);

CREATE TABLE "customers" (
    "id" INTEGER,
    "person_type" TEXT,
    "legal_name" TEXT,
    "trade_name" TEXT,
    "tax_id" TEXT,
    "state_registration" TEXT,
    "email" TEXT,
    "phone" TEXT,
    "is_active" BOOLEAN,
    "created_at" TIMESTAMP WITHOUT TIME ZONE,
    "updated_at" TIMESTAMP WITHOUT TIME ZONE
);

CREATE TABLE "employees" (
    "id" INTEGER,
    "full_name" TEXT,
    "cpf" TEXT,
    "email" TEXT,
    "role" TEXT,
    "primary_location_id" INTEGER,
    "hire_date" DATE,
    "termination_date" DATE,
    "is_active" BOOLEAN,
    "created_at" TIMESTAMP WITHOUT TIME ZONE,
    "updated_at" TIMESTAMP WITHOUT TIME ZONE
);

CREATE TABLE "fiscal_invoices" (
    "id" INTEGER,
    "order_id" INTEGER,
    "nfe_number" TEXT,
    "nfe_access_key" TEXT,
    "series" TEXT,
    "issued_at" TIMESTAMP WITHOUT TIME ZONE,
    "status" TEXT,
    "total_amount" NUMERIC,
    "xml_storage_uri" TEXT,
    "created_at" TIMESTAMP WITHOUT TIME ZONE,
    "updated_at" TIMESTAMP WITHOUT TIME ZONE
);

CREATE TABLE "goods_receipt_items" (
    "id" INTEGER,
    "goods_receipt_id" INTEGER,
    "purchase_order_item_id" INTEGER,
    "quantity_received" NUMERIC
);

CREATE TABLE "goods_receipts" (
    "id" INTEGER,
    "purchase_order_id" INTEGER,
    "received_by_employee_id" INTEGER,
    "received_at" TIMESTAMP WITHOUT TIME ZONE,
    "notes" TEXT,
    "created_at" TIMESTAMP WITHOUT TIME ZONE
);

CREATE TABLE "locations" (
    "id" INTEGER,
    "name" TEXT,
    "location_type" TEXT,
    "postal_code" TEXT,
    "street" TEXT,
    "number" TEXT,
    "complement" TEXT,
    "district" TEXT,
    "city" TEXT,
    "state" TEXT,
    "country" TEXT,
    "is_active" BOOLEAN,
    "created_at" TIMESTAMP WITHOUT TIME ZONE,
    "updated_at" TIMESTAMP WITHOUT TIME ZONE
);

CREATE TABLE "order_items" (
    "id" INTEGER,
    "order_id" INTEGER,
    "product_variant_id" INTEGER,
    "quantity" INTEGER,
    "unit_price" NUMERIC,
    "icms_rate" NUMERIC,
    "ipi_rate" NUMERIC,
    "line_total" NUMERIC
);

CREATE TABLE "orders" (
    "id" INTEGER,
    "order_number" TEXT,
    "channel" TEXT,
    "customer_id" INTEGER,
    "salesperson_id" INTEGER,
    "location_id" INTEGER,
    "status" TEXT,
    "subtotal" NUMERIC,
    "discount_amount" NUMERIC,
    "total" NUMERIC,
    "placed_at" TIMESTAMP WITHOUT TIME ZONE,
    "created_at" TIMESTAMP WITHOUT TIME ZONE,
    "updated_at" TIMESTAMP WITHOUT TIME ZONE
);

CREATE TABLE "payments" (
    "id" INTEGER,
    "order_id" INTEGER,
    "method" TEXT,
    "installments" INTEGER,
    "amount" NUMERIC,
    "status" TEXT,
    "paid_at" TIMESTAMP WITHOUT TIME ZONE,
    "created_at" TIMESTAMP WITHOUT TIME ZONE,
    "updated_at" TIMESTAMP WITHOUT TIME ZONE
);

CREATE TABLE "product_suppliers" (
    "product_variant_id" INTEGER,
    "supplier_id" INTEGER,
    "supplier_sku" TEXT,
    "last_quoted_cost" NUMERIC,
    "lead_time_days" INTEGER,
    "is_preferred" BOOLEAN,
    "created_at" TIMESTAMP WITHOUT TIME ZONE,
    "updated_at" TIMESTAMP WITHOUT TIME ZONE
);

CREATE TABLE "product_variants" (
    "id" INTEGER,
    "product_id" INTEGER,
    "sku" TEXT,
    "barcode_ean" TEXT,
    "sale_price" NUMERIC,
    "cost_price" NUMERIC,
    "weight_kg" NUMERIC,
    "icms_rate" NUMERIC,
    "ipi_rate" NUMERIC,
    "is_active" BOOLEAN,
    "created_at" TIMESTAMP WITHOUT TIME ZONE,
    "updated_at" TIMESTAMP WITHOUT TIME ZONE
);

CREATE TABLE "products" (
    "id" INTEGER,
    "name" TEXT,
    "description" TEXT,
    "brand_id" INTEGER,
    "category_id" INTEGER,
    "ncm_code" TEXT,
    "unit_of_measure" TEXT,
    "is_active" BOOLEAN,
    "created_at" TIMESTAMP WITHOUT TIME ZONE,
    "updated_at" TIMESTAMP WITHOUT TIME ZONE
);

CREATE TABLE "purchase_order_items" (
    "id" INTEGER,
    "purchase_order_id" INTEGER,
    "product_variant_id" INTEGER,
    "quantity_ordered" INTEGER,
    "unit_cost" NUMERIC,
    "line_total" NUMERIC
);

CREATE TABLE "purchase_orders" (
    "id" INTEGER,
    "po_number" TEXT,
    "supplier_id" INTEGER,
    "buyer_id" INTEGER,
    "destination_location_id" INTEGER,
    "status" TEXT,
    "currency" TEXT,
    "subtotal" NUMERIC,
    "total" NUMERIC,
    "placed_at" TIMESTAMP WITHOUT TIME ZONE,
    "expected_delivery_at" DATE,
    "created_at" TIMESTAMP WITHOUT TIME ZONE,
    "updated_at" TIMESTAMP WITHOUT TIME ZONE
);

CREATE TABLE "return_items" (
    "id" INTEGER,
    "return_id" INTEGER,
    "order_item_id" INTEGER,
    "quantity" NUMERIC,
    "action" TEXT,
    "exchange_variant_id" INTEGER,
    "unit_refund_amount" NUMERIC
);

CREATE TABLE "returns" (
    "id" INTEGER,
    "return_number" TEXT,
    "order_id" INTEGER,
    "customer_id" INTEGER,
    "received_at_location_id" INTEGER,
    "status" TEXT,
    "reason" TEXT,
    "total_refund_amount" NUMERIC,
    "created_at" TIMESTAMP WITHOUT TIME ZONE,
    "updated_at" TIMESTAMP WITHOUT TIME ZONE
);

CREATE TABLE "stock_levels" (
    "product_variant_id" INTEGER,
    "location_id" INTEGER,
    "quantity_on_hand" NUMERIC,
    "reorder_point" TEXT,
    "updated_at" TIMESTAMP WITHOUT TIME ZONE
);

CREATE TABLE "stock_movements" (
    "id" INTEGER,
    "product_variant_id" INTEGER,
    "location_id" INTEGER,
    "movement_type" TEXT,
    "quantity" NUMERIC,
    "reference_table" TEXT,
    "reference_id" INTEGER,
    "employee_id" INTEGER,
    "notes" TEXT,
    "occurred_at" TIMESTAMP WITHOUT TIME ZONE,
    "created_at" TIMESTAMP WITHOUT TIME ZONE
);

CREATE TABLE "suppliers" (
    "id" INTEGER,
    "legal_name" TEXT,
    "trade_name" TEXT,
    "country" TEXT,
    "tax_id" TEXT,
    "tax_id_type" TEXT,
    "email" TEXT,
    "phone" TEXT,
    "contact_name" TEXT,
    "is_active" BOOLEAN,
    "created_at" TIMESTAMP WITHOUT TIME ZONE,
    "updated_at" TIMESTAMP WITHOUT TIME ZONE
);

CREATE TABLE "variant_attribute_values" (
    "product_variant_id" INTEGER,
    "attribute_id" INTEGER,
    "value" TEXT
);

COMMIT;
