-- Questão 5 - Média de vendas por dia da semana
--
-- placed_at representa o momento da venda. O calendário vai da menor até a
-- maior data encontrada no arquivo, sem retirar fins de semana.

WITH limites_periodo AS (
    SELECT
        MIN(o.placed_at::date) AS data_inicial,
        MAX(o.placed_at::date) AS data_final
    FROM orders AS o
),
dim_calendario AS (
    SELECT
        serie.data_calendario::date AS data,
        EXTRACT(YEAR FROM serie.data_calendario)::integer AS ano,
        EXTRACT(MONTH FROM serie.data_calendario)::integer AS mes,
        EXTRACT(DAY FROM serie.data_calendario)::integer AS dia,
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
vendas_diarias_pos AS (
    SELECT
        o.placed_at::date AS data_venda,
        SUM(o.total) AS total_vendas
    FROM orders AS o
    WHERE o.channel = 'pos'
    GROUP BY o.placed_at::date
),
calendario_com_vendas AS (
    SELECT
        dc.data,
        dc.numero_dia_semana,
        dc.dia_semana,
        COALESCE(vdp.total_vendas, 0::numeric) AS total_vendas,
        vdp.data_venda IS NULL AS dia_sem_registro
    FROM dim_calendario AS dc
    LEFT JOIN vendas_diarias_pos AS vdp
        ON vdp.data_venda = dc.data
),
medias_por_dia_semana AS (
    SELECT
        cv.numero_dia_semana,
        cv.dia_semana,
        COUNT(*) AS dias_no_calendario,
        COUNT(*) FILTER (WHERE cv.dia_sem_registro) AS dias_sem_venda,
        AVG(cv.total_vendas) AS media_vendas_diarias
    FROM calendario_com_vendas AS cv
    GROUP BY
        cv.numero_dia_semana,
        cv.dia_semana
)
SELECT
    mds.dia_semana,
    mds.dias_no_calendario,
    mds.dias_sem_venda,
    ROUND(mds.media_vendas_diarias, 2) AS media_vendas_diarias
FROM medias_por_dia_semana AS mds
-- A primeira linha indica o dia com a pior média.
ORDER BY
    mds.media_vendas_diarias ASC,
    mds.numero_dia_semana ASC;
