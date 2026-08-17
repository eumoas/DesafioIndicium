-- Questão 4.1 - Clientes com maior ticket médio e diversidade
--
-- As métricas de pedidos são calculadas antes do join com os itens.
-- Isso evita repetir o valor total de um pedido para cada item comprado.
-- Não filtrei status porque o enunciado não informou quais representam venda.

WITH metricas_pedidos AS (
    SELECT
        o.customer_id,
        SUM(o.total) AS faturamento_total,
        COUNT(o.id) AS frequencia,
        SUM(o.total) / COUNT(o.id) AS ticket_medio
    FROM orders AS o
    GROUP BY o.customer_id
),
diversidade_clientes AS (
    SELECT
        o.customer_id,
        COUNT(DISTINCT p.category_id) AS diversidade_categorias
    FROM orders AS o
    INNER JOIN order_items AS oi
        ON oi.order_id = o.id
    INNER JOIN product_variants AS pv
        ON pv.id = oi.product_variant_id
    INNER JOIN products AS p
        ON p.id = pv.product_id
    GROUP BY o.customer_id
),
top_10_clientes AS (
    SELECT
        mp.customer_id,
        mp.faturamento_total,
        mp.frequencia,
        mp.ticket_medio,
        dc.diversidade_categorias
    FROM metricas_pedidos AS mp
    INNER JOIN diversidade_clientes AS dc
        ON dc.customer_id = mp.customer_id
    WHERE dc.diversidade_categorias >= 13
    ORDER BY
        mp.ticket_medio DESC NULLS LAST,
        mp.customer_id ASC
    LIMIT 10
)
SELECT
    tc.customer_id,
    tc.faturamento_total,
    tc.frequencia,
    ROUND(tc.ticket_medio, 2) AS ticket_medio,
    tc.diversidade_categorias
FROM top_10_clientes AS tc
-- O valor exato define o ranking; o arredondamento é só para exibição.
ORDER BY
    tc.ticket_medio DESC NULLS LAST,
    tc.customer_id ASC;
