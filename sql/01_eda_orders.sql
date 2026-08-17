-- Questao 1 - EDA da tabela orders
--
-- Estou considerando que a tabela ja foi importada com os valores monetarios
-- como numericos e as datas como timestamps. Tambem considerei que os campos
-- vazios do CSV viraram NULL durante a importacao.
--
-- Nao filtrei nenhum status porque o enunciado pede para observar a tabela
-- como ela esta. A parte de percentis usa PERCENTILE_CONT, entao pode precisar
-- de ajuste dependendo do banco usado.

-- Comecei reunindo em uma consulta todos os resultados pedidos nas partes 1 e 2.
SELECT
    COUNT(*) AS quantidade_total_linhas,
    MIN(created_at) AS created_at_minimo,
    MAX(created_at) AS created_at_maximo,
    MIN(total) AS total_minimo,
    MAX(total) AS total_maximo,
    AVG(total) AS total_medio
FROM orders;

-- Fiz esta conferencia porque AVG(total) nao considera valores NULL.
SELECT
    COUNT(*) AS quantidade_total_linhas,
    COUNT(total) AS totais_usados_na_media,
    COUNT(*) - COUNT(total) AS total_nulos,
    COUNT(*) - COUNT(created_at) AS created_at_nulos
FROM orders;

-- Depois olhei os nulos de cada coluna para ter uma visao geral da tabela.
-- Aqui eu so conto os valores; nao substituo nem removo nada.
SELECT
    COUNT(*) - COUNT(id) AS id_nulos,
    COUNT(*) - COUNT(order_number) AS order_number_nulos,
    COUNT(*) - COUNT(channel) AS channel_nulos,
    COUNT(*) - COUNT(customer_id) AS customer_id_nulos,
    COUNT(*) - COUNT(salesperson_id) AS salesperson_id_nulos,
    COUNT(*) - COUNT(location_id) AS location_id_nulos,
    COUNT(*) - COUNT(status) AS status_nulos,
    COUNT(*) - COUNT(subtotal) AS subtotal_nulos,
    COUNT(*) - COUNT(discount_amount) AS discount_amount_nulos,
    COUNT(*) - COUNT(total) AS total_nulos,
    COUNT(*) - COUNT(placed_at) AS placed_at_nulos,
    COUNT(*) - COUNT(created_at) AS created_at_nulos,
    COUNT(*) - COUNT(updated_at) AS updated_at_nulos
FROM orders;

-- Como salesperson_id foi a coluna com mais ausencias, separei por canal para
-- entender se existe algum padrao.
SELECT
    channel,
    COUNT(*) AS quantidade_pedidos,
    COUNT(*) - COUNT(salesperson_id) AS salesperson_id_ausentes
FROM orders
GROUP BY channel
ORDER BY channel;

-- Estes testes sao verificacoes que parecem fazer sentido olhando as colunas,
-- mas ainda precisam ser confirmados com a regra de negocio.
SELECT
    SUM(CASE WHEN subtotal < 0 THEN 1 ELSE 0 END) AS subtotais_negativos,
    SUM(CASE WHEN total < 0 THEN 1 ELSE 0 END) AS totais_negativos,
    SUM(CASE WHEN total = 0 THEN 1 ELSE 0 END) AS totais_zerados,
    SUM(
        CASE
            WHEN discount_amount < 0 OR discount_amount > subtotal THEN 1
            ELSE 0
        END
    ) AS descontos_fora_da_faixa,
    SUM(
        CASE
            -- Usei um centavo como diferenca minima para evitar ruido de precisao.
            WHEN ABS(subtotal - discount_amount - total) >= 0.01 THEN 1
            ELSE 0
        END
    ) AS divergencias_na_composicao_total,
    SUM(CASE WHEN placed_at > created_at THEN 1 ELSE 0 END)
        AS placed_at_posterior_a_created_at,
    SUM(CASE WHEN created_at > updated_at THEN 1 ELSE 0 END)
        AS created_at_posterior_a_updated_at,
    SUM(
        CASE
            WHEN placed_at = created_at AND created_at = updated_at THEN 1
            ELSE 0
        END
    ) AS tres_timestamps_identicos
FROM orders;

-- id e order_number parecem identificadores. Por isso conferi se algum valor
-- aparece mais de uma vez.
WITH ids_duplicados AS (
    SELECT id
    FROM orders
    GROUP BY id
    HAVING COUNT(*) > 1
),
numeros_duplicados AS (
    SELECT order_number
    FROM orders
    GROUP BY order_number
    HAVING COUNT(*) > 1
)
SELECT
    (SELECT COUNT(*) FROM ids_duplicados) AS ids_com_duplicidade,
    (SELECT COUNT(*) FROM numeros_duplicados)
        AS order_numbers_com_duplicidade;

-- Tambem conferi as lacunas entre o menor e o maior id. Uma lacuna nao quer
-- dizer necessariamente que existe um pedido perdido.
SELECT
    MIN(id) AS id_minimo,
    MAX(id) AS id_maximo,
    COUNT(DISTINCT id) AS ids_distintos,
    MAX(id) - MIN(id) + 1 - COUNT(DISTINCT id) AS ids_ausentes_no_intervalo
FROM orders;

-- Para nao decidir que o maior valor e um outlier apenas olhando o maximo,
-- usei o metodo de Tukey com 1,5 vezes o intervalo interquartil.
-- Os registros encontrados sao apenas candidatos para investigacao.
WITH quartis AS (
    SELECT
        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY total) AS q1,
        PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY total) AS mediana,
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY total) AS q3
    FROM orders
),
limites AS (
    SELECT
        q1,
        mediana,
        q3,
        q1 - 1.5 * (q3 - q1) AS limite_inferior,
        q3 + 1.5 * (q3 - q1) AS limite_superior
    FROM quartis
)
SELECT
    l.q1,
    l.mediana,
    l.q3,
    l.limite_inferior,
    l.limite_superior,
    COUNT(o.total) AS totais_avaliados,
    SUM(
        CASE
            WHEN o.total < l.limite_inferior
              OR o.total > l.limite_superior THEN 1
            ELSE 0
        END
    ) AS candidatos_a_outlier
FROM orders AS o
CROSS JOIN limites AS l
GROUP BY
    l.q1,
    l.mediana,
    l.q3,
    l.limite_inferior,
    l.limite_superior;

-- Por ultimo, separei os valores por status. Isso ajuda a lembrar que a media
-- geral tambem inclui pedidos cancelados e em rascunho.
SELECT
    status,
    COUNT(*) AS quantidade_pedidos,
    MIN(total) AS total_minimo,
    MAX(total) AS total_maximo,
    AVG(total) AS total_medio
FROM orders
GROUP BY status
ORDER BY quantidade_pedidos DESC;
