SELECT
    COUNT(*) AS quantidade_total_linhas,
    MIN(created_at) AS created_at_minimo,
    MAX(created_at) AS created_at_maximo,
    MIN(total) AS total_minimo,
    MAX(total) AS total_maximo,
    AVG(total) AS total_medio
FROM orders;