# Questão 5 — Dimensão de calendário

## Decisão executiva

A solução cria uma dimensão de datas entre a menor e a maior `placed_at` do
arquivo, agrega as vendas `pos` no grão diário e parte do calendário para fazer
um `LEFT JOIN` com essas vendas. Quando não existe pedido físico em uma data, o
valor diário é convertido de `NULL` para zero antes do cálculo da média.

Considerando todos os status, como determina a leitura literal do enunciado, a
menor média é a de **Quinta-feira: R$ 157.154,32**.

Esse resultado é descritivo. A diferença para Domingo é de apenas R$ 461,81, ou
aproximadamente 0,29%, e não sustenta sozinha uma decisão de fechar lojas.

## 1. Entendimento do problema

O problema do cálculo do estagiário é a ausência de datas sem vendas. Uma
agregação feita somente sobre `orders` enxerga apenas dias que possuem ao menos
um registro. Como `AVG` também ignora `NULL`, os dias abertos com faturamento
zero não entram no denominador e a média fica inflada.

### Requisitos explícitos

- considerar todas as datas entre a menor e a data de venda mais recente do
  arquivo;
- assumir que a operação abriu todos os dias, inclusive finais de semana;
- considerar lojas físicas como `channel = 'pos'`;
- atribuir zero aos dias sem registro;
- calcular vendas diárias com `SUM(total)` por data;
- calcular a média por dia da semana usando todos os dias do calendário;
- apresentar os nomes dos dias em português;
- construir e relacionar uma dimensão de datas usando SQL.

### Requisitos inferidos

- `placed_at` representa a data da venda;
- “data atual da venda presente no arquivo” significa `MAX(placed_at)`, e não
  `CURRENT_DATE`;
- a análise pedida está no grão da rede física por dia, não de cada unidade por
  dia;
- o calendário precisa ser a tabela da esquerda no relacionamento;
- o filtro de canal deve ocorrer antes do `LEFT JOIN`;
- primeiro é necessário somar pedidos por data e somente depois calcular a
  média semanal;
- o valor não arredondado deve definir a ordenação.

### Ambiguidades que mudariam o resultado

- quais status representam vendas válidas;
- se “loja física” deve ser definida pelo canal ou por
  `locations.location_type`;
- se o resultado deve ser da rede ou separado por unidade;
- se o limite superior é a maior data do snapshot ou o dia da execução;
- qual fuso horário determina a data local da venda;
- se fechar significa avaliar faturamento, margem ou resultado operacional.

## 2. Premissas e hipóteses

| Premissa ingênua | Problema | Decisão adotada |
|---|---|---|
| `AVG(total)` por dia da semana mede vendas diárias | Mede o valor médio por pedido | Fazer `SUM(total)` por data antes do `AVG` |
| Datas sem venda aparecerão no agrupamento | Elas não existem em `orders` | Gerar todas as datas explicitamente |
| Um `LEFT JOIN` sozinho preserva zeros | Um filtro de `orders` no `WHERE` final pode eliminá-los | Filtrar `pos` na CTE de vendas |
| `AVG(NULL)` considera zero | O PostgreSQL ignora `NULL` | Aplicar `COALESCE(..., 0)` antes da média |
| `TO_CHAR` sempre devolve português | O resultado depende de `lc_time` | Usar `ISODOW` e `CASE` explícito |
| `CURRENT_DATE` é o fim do arquivo | O snapshot possui datas até dezembro de 2026 | Usar `MAX(placed_at::date)` |
| Todo `pos` está em uma location do tipo `store` | Há POS associado a warehouses | Respeitar a definição explícita `channel = 'pos'` |
| Menor faturamento significa prejuízo | Faltam custos e margem | Responder a média sem recomendar fechamento |

Nenhum status foi filtrado porque essa regra não foi fornecida. Timestamps sem
fuso foram interpretados como já representando o dia local relevante para a
análise.

## 3. O que não está óbvio

### Existem dois níveis de agregação

O cálculo correto precisa obedecer a esta sequência:

```text
pedidos -> soma por data -> inclusão de datas zeradas -> média por dia da semana
```

Fazer `AVG(orders.total)` diretamente produz ticket médio por transação. Mesmo
agregar vendas somente nos dias existentes e depois calcular a média ainda
exclui dias sem venda.

### O lado e a posição dos filtros importam

A população que deve ser preservada é o calendário. Portanto, ele fica à
esquerda:

```sql
FROM dim_calendario AS dc
LEFT JOIN vendas_diarias_pos AS vdp
    ON vdp.data_venda = dc.data
```

Se `orders.channel = 'pos'` fosse colocado em um `WHERE` depois desse join, as
linhas sem correspondência seriam removidas e o problema original voltaria.
Por isso, o canal é filtrado dentro da agregação `vendas_diarias_pos`.

### Zero e ausência de registro não são exatamente a mesma coisa

`COALESCE(total_vendas, 0)` cria o valor necessário para a média. Para contar
os dias sem registro, a consulta usa `vdp.data_venda IS NULL`, em vez de
`total_vendas = 0`. Assim, um dia que tivesse registros cuja soma fosse zero não
seria classificado incorretamente como ausência de venda.

### O arquivo e a data corrente divergem

O snapshot cobre `2020-01-01` a `2026-12-31`, totalizando 2.557 dias. A data do
ambiente durante a análise é 16 de agosto de 2026 e existem registros
posteriores a ela. Usar `CURRENT_DATE` tornaria a consulta variável e excluiria
parte do arquivo. A interpretação adotada foi a data mais atual presente na
fonte, isto é, `MAX(placed_at)`.

### Canal e tipo de local são inconsistentes

Existem 14.656 pedidos `pos`:

- 7.161 associados a locations do tipo `store`;
- 7.495 associados a locations do tipo `warehouse`.

Como o enunciado define explicitamente lojas físicas como `pos`, não foi
adicionado um join com `locations`. Filtrar também `location_type = 'store'`
mudaria a regra e faria Domingo aparecer como o pior dia.

### Rede e loja individual são perguntas diferentes

A consulta soma todo o canal físico por data. Uma venda em qualquer unidade faz
o dia ter faturamento para a rede. Para decidir o fechamento de cada loja seria
necessário gerar a combinação `calendário x location_id`, preencher os
loja-dias sem vendas e calcular uma média por unidade.

Entre as três locations classificadas como `store`, o pior dia não é igual:

- Loja Leão: Quinta-feira;
- Loja Oliveira: Terça-feira;
- Loja Mendonça: Sábado.

Portanto, a conclusão agregada não deve ser aplicada automaticamente a todas as
unidades.

### Status altera a conclusão

A consulta considera `paid`, `confirmed`, `cancelled` e `draft` porque o
enunciado não definiu exclusões. Se fossem considerados somente pedidos
`paid`, Domingo passaria a ter a menor média. Essa é uma regra que Marina deve
validar antes de usar o resultado operacionalmente.

### Escala e manutenção

`generate_series` cria apenas 2.557 linhas, um custo irrelevante diante das
48.998 vendas. Uma dimensão física permanente faria sentido se fosse reutilizada
por dashboards e enriquecida com feriados, períodos fiscais e dias especiais.
Para uma consulta pontual, uma CTE é mais simples e não cria estado adicional.

## 4. Alternativas consideradas

### A — CTE com `generate_series` (escolhida)

- **Quando faz sentido:** análise PostgreSQL pontual com limites vindos dos
  próprios dados.
- **Vantagens:** simples, determinística, reproduzível e sem tabela auxiliar.
- **Desvantagens:** recalcula o calendário a cada execução.
- **Complexidade:** baixa.
- **Risco:** uma data máxima inválida e muito distante poderia gerar uma série
  excessiva.
- **Sacrifício:** não centraliza feriados ou calendário fiscal.

### B — Tabela permanente `dim_calendario`

- **Quando faz sentido:** BI recorrente e várias tabelas fato usando o mesmo
  calendário.
- **Vantagens:** definição centralizada, feriados, ano fiscal e reutilização.
- **Desvantagens:** exige chave, carga inicial, extensão futura e governança.
- **Complexidade:** média.
- **Risco:** ficar desatualizada ou divergir entre ambientes.
- **Sacrifício:** simplicidade para esta entrega isolada.

### C — CTE recursiva

- **Quando faz sentido:** bancos sem uma função equivalente a
  `generate_series`.
- **Vantagens:** usa construção SQL amplamente conhecida.
- **Desvantagens:** mais extensa e menos direta no PostgreSQL.
- **Complexidade:** média sem benefício neste banco.
- **Sacrifício:** legibilidade.

### D — Calendário por unidade

- **Quando faz sentido:** decisão de funcionamento loja a loja.
- **Vantagens:** não deixa vendas de uma unidade esconderem zeros de outra.
- **Desvantagens:** muda o grão e responde outra pergunta.
- **Complexidade:** ainda baixa para seis locations, mas exige uma definição
  confiável de quais locations são lojas.
- **Sacrifício:** comparabilidade direta com a regra agregada solicitada.

## 5. Olhar de avaliador

Uma resposta apenas sintaticamente correta provavelmente faria
`GROUP BY EXTRACT(DOW FROM placed_at)` diretamente em `orders`. Isso não resolve
nem o grão diário nem a ausência de datas.

Decisões que demonstram maturidade:

- declarar `placed_at` como data do evento;
- construir um calendário inclusivo entre `MIN` e `MAX`;
- agregar pedidos por data antes da média;
- preservar o calendário com `LEFT JOIN`;
- aplicar `COALESCE` antes do `AVG`;
- separar “dia sem registro” de “soma igual a zero”;
- usar nomes em português sem depender do locale;
- ordenar pela média exata e arredondar apenas a saída;
- reconciliar a soma diária com a soma original de POS;
- registrar as ambiguidades de status, location e período;
- não transformar menor faturamento em recomendação de fechamento.

Erros que eu penalizaria:

- `AVG(total)` direto por dia da semana;
- calendário relacionado diretamente a cada pedido, sem agregação diária;
- `INNER JOIN` com o calendário;
- filtro de POS depois do `LEFT JOIN`;
- ausência de `COALESCE`;
- `TO_CHAR(..., 'Day')` assumindo idioma português;
- usar `CURRENT_DATE` sem explicar;
- filtrar `location_type = 'store'` ignorando a definição `= pos`;
- excluir cancelados e rascunhos sem regra;
- recomendar fechamento apenas pela menor média.

## 6. Design thinking, arquitetura e decisões

### Empatizar

- **Gabriel Santos:** recebe granularidade explícita, CTEs pequenas, nomes
  previsíveis, reconciliação e premissas documentadas.
- **Marina Costa:** recebe o impacto de status, a diferença entre faturamento e
  rentabilidade e o alerta de que cada loja possui comportamento distinto.
- **Sr. Almir:** consegue comparar o cálculo ingênuo com o corrigido e verificar
  quantos zeros entraram no denominador, sem depender de nuvem ou algoritmo
  opaco.

### Definir

O problema não é traduzir o nome do dia nem apenas agrupar vendas. É construir
a população correta de dias abertos antes de calcular a média.

### Fluxo

```text
orders -> MIN/MAX placed_at -> generate_series -> dimensão calendário

orders -- filtro pos --> SUM(total) por data --------+
                                                    |
calendário ------------------------------------ LEFT JOIN
                                                    |
                                      COALESCE(ausência, zero)
                                                    |
                                   AVG por ISODOW e nome português
```

### Decisões com trade-off

- a dimensão é derivada, não persistida;
- os limites vêm da fonte completa e o canal é aplicado apenas às vendas;
- a análise agrega a rede, não cada unidade;
- todos os status permanecem por falta de contrato;
- `CASE` repete sete nomes, mas evita dependência ambiental de locale;
- a saída mostra os sete dias, ordenados do pior para o melhor, em vez de
  esconder o contexto com `LIMIT 1`.

## 7. Implementação

Arquivo: [`sql/questao_5.sql`](../sql/questao_5.sql).

A consulta devolve:

| Dia | Dias no calendário | Dias sem venda | Média diária |
|---|---:|---:|---:|
| **Quinta-feira** | **366** | **20** | **R$ 157.154,32** |
| Domingo | 365 | 12 | R$ 157.616,13 |
| Segunda-feira | 365 | 7 | R$ 158.241,15 |
| Sábado | 365 | 11 | R$ 164.858,27 |
| Terça-feira | 365 | 8 | R$ 166.118,83 |
| Sexta-feira | 365 | 10 | R$ 170.193,68 |
| Quarta-feira | 366 | 10 | R$ 173.605,44 |

Reconciliação do período:

- 2.557 dias;
- 2.479 datas com pelo menos uma venda POS;
- 78 datas sem venda POS;
- 14.656 pedidos POS;
- R$ 419.273.315,30 na soma de `orders.total` para POS.

A versão que calcula a média apenas nos dias com venda daria, por exemplo,
R$ 166.238,38 para Quinta-feira. A inclusão dos 20 dias zerados reduz essa
média para R$ 157.154,32.

## 8. Estratégia e resultados dos testes

### Testes estruturais do calendário

- `COUNT(*) = data_final - data_inicial + 1`;
- `COUNT(*) = COUNT(DISTINCT data)`;
- presença de exatamente sete números e sete nomes de dia da semana;
- inclusão das duas datas-limite;
- quantidade correta de quartas e quintas em um período que começa numa quarta
  e termina numa quinta.

### Testes do relacionamento

- dia com vários pedidos deve gerar uma única soma diária;
- dia apenas com e-commerce deve valer zero para POS;
- dia sem qualquer pedido deve continuar no resultado;
- filtro de canal no lugar errado deve ser detectado por regressão;
- um dia com registros cuja soma seja zero não deve ser contado como “sem
  registro”;
- `SUM(total_vendas)` após o calendário deve reconciliar com
  `SUM(total) WHERE channel = 'pos'`.

### Testes de regra e casos-limite

- período começando ou terminando no fim de semana;
- tabela vazia;
- `placed_at` ou `total` nulo;
- data máxima anômala muito distante;
- diferença entre todos os status e somente vendas reconhecidas;
- rede agregada versus calendário por unidade;
- execução em servidor com locale não português;
- ordenação de médias que empatam após arredondamento.

### Validações executadas

Os valores foram recalculados diretamente nos CSVs com aritmética decimal. O
conjunto de datas POS possui 2.479 elementos distintos; a diferença para os
2.557 dias do intervalo confirmou exatamente 78 lacunas. As médias por dia da
semana foram reproduzidas incluindo zero nessas datas.

Não há servidor PostgreSQL neste ambiente. A execução no PostgreSQL continua
sendo necessária para validar `generate_series`, `FILTER` e o plano real no
banco definido pelo desafio.

## 9. Autocrítica

A consulta responde corretamente qual dia possui a menor média agregada de
vendas POS, mas não responde se uma loja deveria fechar.

Limitações principais:

- faturamento não é lucro ou margem;
- custos fixos e variáveis não foram fornecidos;
- status podem incluir vendas não reconhecidas;
- devoluções não são descontadas;
- a diferença entre Quinta e Domingo é muito pequena;
- a dispersão entre datas é muito maior que a diferença das médias;
- sazonalidade, feriados e promoções não são controlados;
- vendas podem migrar para outro dia ou para o e-commerce após um fechamento;
- a rede agregada esconde comportamentos diferentes por unidade;
- timestamps sem fuso podem atribuir vendas próximas da meia-noite ao dia
  incorreto;
- a extração contém datas posteriores ao dia da análise.

Uma evolução útil para a decisão incluiria margem, custo de abertura, feriados,
sazonalidade, análise por loja e intervalo de incerteza. Essa seria outra
pergunta, com dados e regras adicionais.

Melhorias que podem valer a pena em uso recorrente:

- dimensão permanente com feriados e calendário fiscal;
- fato diário por unidade e canal;
- definição formal de status válidos;
- testes de limites temporais e reconciliação automatizados;
- análise de margem e custos por loja-dia.

Não valem a complexidade nesta entrega:

- criar uma tabela calendário permanente apenas para esta consulta;
- adicionar framework de transformação;
- usar Python para gerar datas que o PostgreSQL gera nativamente;
- criar índices sem observar o plano;
- aplicar modelo estatístico dentro do SQL obrigatório;
- escolher um dia para fechamento com base apenas no ranking.

## 10. Perguntas que eu deveria conseguir responder

1. **Por que `AVG(total)` direto está errado?**  
   Ele mede pedido médio, não a média da soma diária.

2. **Por que agregar por data antes do join com o calendário?**  
   Para manter uma linha por dia e dar o mesmo peso a cada dia aberto.

3. **Por que o calendário fica do lado esquerdo?**  
   Ele define toda a população de datas que precisa sobreviver ao join.

4. **Por que `COALESCE` precisa ocorrer antes do `AVG`?**  
   Porque `AVG` ignora `NULL`, mas a regra determina que ausência vale zero.

5. **Por que o filtro de POS não está no `WHERE` final?**  
   Porque isso eliminaria as linhas sem correspondência produzidas pelo
   `LEFT JOIN`.

6. **Por que usar `placed_at`?**  
   É o momento semântico da venda; `created_at` descreve criação do registro.

7. **Por que usar `MAX(placed_at)` e não `CURRENT_DATE`?**  
   Para respeitar todo o snapshot e manter a consulta reproduzível.

8. **Por que não usar `TO_CHAR` para o nome do dia?**  
   O idioma depende da configuração do servidor; `ISODOW` e `CASE` são
   determinísticos.

9. **Por que não filtrar `locations.location_type = 'store'`?**  
   O enunciado define físico como `pos`, e os dados apresentam conflito entre
   canal e tipo de local.

10. **Por que todos os status foram incluídos?**  
    Não há definição de venda reconhecida. Excluir status mudaria a resposta e
    seria uma regra inventada.

11. **Quinta-feira é realmente pior que Domingo?**  
    Descritivamente sim, por R$ 461,81. A proximidade e a alta variação não
    permitem concluir uma diferença operacional relevante sem análise adicional.

12. **A rede deve fechar na quinta?**  
    O SQL não sustenta essa decisão. É preciso analisar cada loja, margens,
    custos, sazonalidade e deslocamento da demanda.

13. **Quando uma dimensão persistente seria melhor?**  
    Quando várias análises e fatos reutilizarem calendário, feriados e períodos
    fiscais sob governança comum.

14. **Como provar que os zeros foram realmente incluídos?**  
    Reconciliar quantidade de datas, dias sem correspondência e soma total antes
    e depois do join.
