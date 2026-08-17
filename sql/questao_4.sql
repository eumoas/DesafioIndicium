-- Questão 4 - Análise de clientes
--
-- As métricas financeiras são calculadas antes do join com order_items.
-- Assim, o total de um pedido não é repetido para cada item comprado.
-- Nenhum status foi filtrado porque o enunciado não definiu essa regra.

-- Resultado 1: dez clientes que atendem ao critério de diversidade.
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
-- A ordenação usa o valor exato; o arredondamento é apenas para exibição.
ORDER BY
    tc.ticket_medio DESC NULLS LAST,
    tc.customer_id ASC;


-- Resultado 2: categoria com maior quantidade entre os dez clientes.
-- As CTEs são repetidas porque cada SELECT possui seu próprio escopo.
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
        mp.ticket_medio
    FROM metricas_pedidos AS mp
    INNER JOIN diversidade_clientes AS dc
        ON dc.customer_id = mp.customer_id
    WHERE dc.diversidade_categorias >= 13
    ORDER BY
        mp.ticket_medio DESC NULLS LAST,
        mp.customer_id ASC
    LIMIT 10
),
quantidade_por_categoria AS (
    SELECT
        p.category_id,
        SUM(oi.quantity) AS quantidade_total
    FROM top_10_clientes AS tc
    INNER JOIN orders AS o
        ON o.customer_id = tc.customer_id
    INNER JOIN order_items AS oi
        ON oi.order_id = o.id
    INNER JOIN product_variants AS pv
        ON pv.id = oi.product_variant_id
    INNER JOIN products AS p
        ON p.id = pv.product_id
    GROUP BY p.category_id
),
categorias_ranqueadas AS (
    SELECT
        qpc.category_id,
        qpc.quantidade_total,
        DENSE_RANK() OVER (
            ORDER BY qpc.quantidade_total DESC
        ) AS posicao
    FROM quantidade_por_categoria AS qpc
)
SELECT
    cr.category_id,
    c.name AS categoria,
    cr.quantidade_total
FROM categorias_ranqueadas AS cr
INNER JOIN categories AS c
    ON c.id = cr.category_id
WHERE cr.posicao = 1
-- Se duas categorias liderarem, ambas serão apresentadas.
ORDER BY cr.category_id ASC;
