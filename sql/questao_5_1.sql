-- Questão 5.1 - Calendário e média diária de vendas
--
-- Usei placed_at por representar a data em que a venda aconteceu.
-- O período vai da primeira até a última data encontrada no arquivo.
-- Mantive todos os status porque o enunciado não definiu exclusões.

WITH limites_periodo AS (
    SELECT
        MIN(o.placed_at::date) AS data_inicial,
        MAX(o.placed_at::date) AS data_final
    FROM orders AS o
),
calendario AS (
    SELECT
        serie.data_calendario::date AS data,
        EXTRACT(ISODOW FROM serie.data_calendario)::integer AS numero_dia_semana,
        CASE EXTRACT(ISODOW FROM serie.data_calendario)::integer
            WHEN 1 THEN 'Segunda-feira'
            WHEN 2 THEN 'Terça-feira'
            WHEN 3 THEN 'Quarta-feira'
            WHEN 4 THEN 'Quinta-feira'
            WHEN 5 THEN 'Sexta-feira'
            WHEN 6 THEN 'Sábado'
            WHEN 7 THEN 'Domingo'
        END AS dia_semana
    FROM limites_periodo AS lp
    CROSS JOIN LATERAL generate_series(
        lp.data_inicial::timestamp,
        lp.data_final::timestamp,
        INTERVAL '1 day'
    ) AS serie(data_calendario)
),
vendas_por_dia AS (
    SELECT
        o.placed_at::date AS data_venda,
        SUM(o.total) AS valor_venda
    FROM orders AS o
    WHERE o.channel = 'pos'
    GROUP BY o.placed_at::date
),
calendario_com_vendas AS (
    SELECT
        c.data,
        c.numero_dia_semana,
        c.dia_semana,
        COALESCE(vpd.valor_venda, 0::numeric) AS valor_venda
    FROM calendario AS c
    LEFT JOIN vendas_por_dia AS vpd
        ON vpd.data_venda = c.data
),
media_por_dia_semana AS (
    SELECT
        cv.numero_dia_semana,
        cv.dia_semana,
        AVG(cv.valor_venda) AS media_venda_diaria
    FROM calendario_com_vendas AS cv
    GROUP BY
        cv.numero_dia_semana,
        cv.dia_semana
)
SELECT
    mds.dia_semana,
    ROUND(mds.media_venda_diaria, 2) AS media_venda_diaria
FROM media_por_dia_semana AS mds
-- O primeiro resultado representa a menor média diária.
ORDER BY
    mds.media_venda_diaria ASC,
    mds.numero_dia_semana ASC;
