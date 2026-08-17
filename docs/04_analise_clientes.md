# Questão 4 — Análise de clientes

## Decisão executiva

O ranking foi calculado em duas granularidades separadas:

- faturamento, frequência e ticket médio no nível de `orders`;
- diversidade e quantidade por categoria no nível de `order_items`.

Essa separação é necessária para que o valor de um pedido não seja repetido
uma vez para cada item. Seguindo literalmente o enunciado, todos os status e
todo o período dos arquivos foram considerados.

A categoria com maior quantidade entre os dez clientes selecionados foi
**Hélices**, `category_id = 8`, com **492** na soma de `quantity`.

## 1. Entendimento do problema

A Diretoria quer encontrar clientes que combinem ticket médio alto com compras
em muitas categorias. Depois de selecionar os dez primeiros, deseja saber qual
categoria aparece com maior quantidade no consumo desse grupo.

### Requisitos explícitos

- faturamento total: `SUM(orders.total)` por cliente;
- frequência: quantidade de IDs de venda por cliente;
- ticket médio: faturamento total dividido pela frequência;
- diversidade: `COUNT(DISTINCT products.category_id)` por cliente;
- manter somente clientes com pelo menos 13 categorias;
- ordenar pelo ticket médio decrescente;
- em empate de ticket, usar `customer_id` crescente;
- selecionar dez clientes;
- para esses dez, somar `order_items.quantity` por categoria e identificar a
  maior.

### Requisitos inferidos

- o caminho até a categoria é `orders -> order_items -> product_variants ->
  products`;
- `category_id` significa a categoria direta do produto, não sua categoria-pai;
- o arredondamento é apenas de apresentação e não deve alterar o ranking;
- a categoria líder deve ser calculada somente depois de fixar os dez clientes;
- empates na liderança de categoria não devem ser escondidos.

### Informações ausentes que mudariam o resultado

- quais status representam uma venda reconhecida;
- qual período deve ser analisado;
- se devoluções devem reduzir faturamento ou quantidade;
- se fidelidade deveria exigir uma frequência mínima ou recorrência temporal;
- como desempatar categorias com a mesma quantidade;
- como comparar quantidades de produtos com unidades de medida diferentes.

## 2. Premissas e hipóteses

| Premissa | Questionamento | Decisão nesta entrega |
|---|---|---|
| Todo registro de `orders` é faturamento | Existem `draft` e `cancelled` | Incluir todos, pois nenhum filtro foi autorizado |
| Um join único resolve todas as métricas | O pedido se repete para cada item | Agregar pedidos e categorias separadamente |
| Frequência é quantidade de itens | Um pedido pode ter vários itens | Contar `orders.id` no grão de pedidos |
| `SUM(DISTINCT total)` corrige duplicação | Pedidos distintos podem ter o mesmo valor | Não usar; corrigir a granularidade |
| A tabela `payments` representa faturamento | Um pedido pode ter vários pagamentos | Não usar; a premissa manda somar `orders.total` |
| Categoria significa categoria-pai | O enunciado cita diretamente `category_id` | Contar `products.category_id` |
| Ticket arredondado pode ordenar o ranking | Valores diferentes podem arredondar para o mesmo número | Ordenar pelo valor exato |
| O termo “fiel” implica muitas compras | A regra não define frequência mínima | Calcular a frequência, mas não inventar um corte |

As chaves utilizadas foram verificadas no snapshot: IDs são únicos e não nulos,
e não há referências órfãs na cadeia de joins. Isso é uma propriedade observada,
não uma garantia do schema atual, que ainda não possui PKs ou FKs.

## 3. O que não está óbvio

### Granularidade e fan-out

Este seria o erro mais grave:

```sql
SELECT
    o.customer_id,
    SUM(o.total)
FROM orders AS o
JOIN order_items AS oi
    ON oi.order_id = o.id
GROUP BY o.customer_id;
```

Cada pedido aparece uma vez por linha de item. Portanto, seu `total` seria
somado repetidamente. Usar `COUNT(DISTINCT o.id)` corrigiria somente a
frequência; o faturamento continuaria inflado. `SUM(DISTINCT o.total)` também é
incorreto, porque dois pedidos legítimos podem possuir exatamente o mesmo
valor.

A solução agrega `orders` antes de qualquer join com itens.

### Status e reconhecimento de receita

A base contém:

| Status | Pedidos |
|---|---:|
| `paid` | 34.365 |
| `confirmed` | 7.335 |
| `cancelled` | 4.847 |
| `draft` | 2.451 |

“Faturamento” normalmente não incluiria rascunhos ou cancelamentos. Entretanto,
o enunciado define o cálculo como soma de `total` e não informa status válidos.
Excluir registros seria introduzir uma regra não fornecida.

A sensibilidade é material:

| Escopo hipotético | Primeiro cliente | Categoria líder |
|---|---:|---|
| Todos os status — resultado entregue | 22 | Hélices, 492 |
| Apenas `paid` e `confirmed` | 300 | Pesca, 344 |
| Apenas `paid` | 1527 | Equipamentos, 291 |

Em uma análise real, esta decisão deve ser confirmada com Negócios antes de
publicar o ranking.

### O critério de elite é pouco seletivo

Existem apenas 14 categorias diretas. Entre os 2.000 clientes:

- 1.771 compraram em 14 categorias;
- 200 compraram em 13;
- 27 compraram em 12;
- 2 compraram em 11.

Assim, 1.971 clientes, ou 98,55%, passam pelo filtro. Na prática, o ranking é
quase totalmente determinado pelo ticket médio. Isso não invalida o cálculo,
mas reduz a força do rótulo “elite”.

### Fidelidade não é completamente medida

A frequência é calculada, mas não participa do filtro nem da ordenação. Em
outro conjunto de dados, uma única compra com 13 categorias e ticket muito alto
poderia colocar um cliente no ranking. Os dez clientes atuais possuem de 16 a
29 pedidos, então o problema não muda o resultado observado, mas continua sendo
uma limitação da definição.

### Outras limitações de interpretação

- não há janela de tempo; clientes com histórico mais longo têm mais chance de
  acumular diversidade;
- a extração se estende até 31 de dezembro de 2026 e foi usada integralmente;
- pagamentos, devoluções e reembolsos não entram, porque não fazem parte da
  fórmula obrigatória;
- produtos das categorias usam `UN`, `PC`, `M` e `L`. A soma de `quantity`
  mistura essas unidades e deve ser lida como a métrica pedida, não como uma
  quantidade física perfeitamente comparável;
- produtos ou categorias atualmente inativos não devem apagar compras
  históricas e, por isso, não foram filtrados;
- a regra não define desempate da categoria. A consulta usa `DENSE_RANK` e
  retorna todas as líderes em caso de empate.

### Escala e performance

O volume atual é pequeno para o PostgreSQL: 48.998 pedidos e 147.320 linhas de
itens. Agregações e hash joins são adequados. Em uma base maior, os primeiros
índices a avaliar seriam as chaves de relacionamento, como
`order_items.order_id`, `orders.customer_id` e
`product_variants.product_id`. A decisão deveria ser guiada por `EXPLAIN
ANALYZE`, não por criação preventiva de índices sem medição.

## 4. Alternativas consideradas

### A — Agregações separadas por granularidade (escolhida)

- **Quando faz sentido:** métricas financeiras estão em pedidos, enquanto a
  diversidade está nos itens.
- **Vantagens:** evita duplicação, deixa o grão explícito e é fácil de testar.
- **Desvantagens:** as CTEs precisam ser repetidas para produzir dois resultados
  independentes.
- **Complexidade:** linear no volume das tabelas envolvidas.
- **Risco:** duplicatas nas dimensões ainda poderiam multiplicar joins; por isso
  as chaves foram validadas.
- **Sacrifício:** alguma repetição textual em troca de duas saídas claras.

### B — Subconsultas correlacionadas por cliente

- **Quando faz sentido:** exploração de poucos clientes.
- **Vantagens:** cada métrica permanece isolada.
- **Desvantagens:** pode repetir leituras de itens e produtos para cada cliente.
- **Complexidade:** SQL aparentemente curto, mas plano potencialmente pior.
- **Risco:** escalar mal sem índices adequados.
- **Sacrifício:** previsibilidade de performance.

### C — Mart materializado de métricas de cliente

- **Quando faz sentido:** dashboard recorrente com várias consultas sobre as
  mesmas métricas.
- **Vantagens:** consultas rápidas e definição centralizada.
- **Desvantagens:** exige atualização, governança e controle de consistência.
- **Complexidade:** maior que a necessária para uma resposta pontual.
- **Sacrifício:** simplicidade e ausência de estado adicional.

Uma única consulta com JSON, arrays ou a categoria repetida em cada linha dos
dez clientes também seria possível, mas produziria uma saída menos legível. Duas
consultas explícitas são mais fáceis de entender e defender.

## 5. Olhar de avaliador

Uma resposta apenas correta encontra o ranking. Uma resposta madura demonstra
por que o ranking não foi corrompido pelos joins e não esconde as limitações da
definição de negócio.

Decisões que demonstram maturidade:

- declarar o grão de cada métrica;
- não juntar `payments` sem necessidade;
- não usar `SUM(DISTINCT total)` como remendo;
- respeitar o caminho variante -> produto -> categoria;
- manter o ticket exato durante a ordenação;
- implementar o desempate solicitado;
- não inventar filtro de status ou período;
- tratar empate de categoria sem escolher uma vencedora arbitrária;
- medir a seletividade do filtro de elite;
- separar cumprimento da regra de avaliação crítica da regra.

Erros prováveis de um candidato mediano:

- somar `orders.total` depois de juntar itens;
- contar linhas de itens como frequência;
- esquecer `DISTINCT` na diversidade;
- ligar `order_items.product_variant_id` diretamente a `products.id`;
- aplicar `LIMIT 10` antes do filtro de diversidade;
- arredondar antes de ordenar;
- calcular a categoria sobre todos os clientes;
- excluir `cancelled` ou `draft` sem explicar;
- transformar a questão em RFM, clustering ou machine learning sem solicitação.

## 6. Design thinking, arquitetura e decisões

### Empatizar

- **Gabriel Santos:** precisa verificar granularidade, relações, premissas e
  desempates em um SQL legível, sem abstrações artificiais.
- **Marina Costa:** precisa saber que o resultado muda radicalmente conforme a
  definição de venda reconhecida e que o corte de 13 categorias qualifica
  98,55% dos clientes.
- **Sr. Almir:** recebe números reconciliáveis, regras explícitas e uma cadeia de
  cálculo que pode ser conferida tabela por tabela.

### Definir

Existem dois problemas diferentes:

1. cumprir exatamente a regra de ranking fornecida;
2. avaliar se essa regra realmente representa fidelidade para uma decisão de
   negócio.

O SQL resolve o primeiro. A documentação torna as limitações do segundo
visíveis, sem modificar silenciosamente a pergunta.

### Fluxo da solução

```text
orders ------------------------> faturamento, frequência e ticket
   |
   +-> order_items -> variants -> products -> diversidade de categorias
                                      |
                         unir métricas por customer_id
                                      |
                    filtrar >= 13 e ordenar ticket exato
                                      |
                                 top 10 clientes
                                      |
             orders -> items -> products -> SUM(quantity) por categoria
```

### Decisões com trade-off

- duas CTEs de agregação evitam fan-out, ao custo de mais de uma leitura lógica;
- repetir as CTEs nos dois `SELECT` evita criar tabela temporária ou view;
- `DENSE_RANK` pode devolver mais de uma categoria, mas não esconde empates;
- `NULLS LAST` torna a ordenação defensiva, embora não existam `total` nulos no
  snapshot;
- o arredondamento para duas casas ocorre apenas na projeção final.

## 7. Implementação

Arquivo: [`sql/questao_4.sql`](../sql/questao_4.sql).

O script produz dois resultados. O primeiro é o ranking:

| Posição | customer_id | Faturamento total | Frequência | Ticket médio | Categorias |
|---:|---:|---:|---:|---:|---:|
| 1 | 22 | 1.087.838,44 | 26 | 41.839,94 | 14 |
| 2 | 1477 | 916.262,58 | 22 | 41.648,30 | 14 |
| 3 | 929 | 1.082.775,89 | 26 | 41.645,23 | 14 |
| 4 | 1116 | 655.737,20 | 16 | 40.983,58 | 14 |
| 5 | 1691 | 815.471,30 | 20 | 40.773,57 | 14 |
| 6 | 774 | 726.127,99 | 18 | 40.340,44 | 14 |
| 7 | 1470 | 1.040.553,09 | 26 | 40.021,27 | 14 |
| 8 | 1599 | 997.616,46 | 25 | 39.904,66 | 14 |
| 9 | 965 | 677.297,78 | 17 | 39.841,05 | 14 |
| 10 | 1722 | 1.146.455,22 | 29 | 39.532,94 | 14 |

O segundo resultado é:

| category_id | categoria | quantidade_total |
|---:|---|---:|
| 8 | Hélices | 492 |

O grupo possui 225 pedidos, 792 linhas de item e soma de 4.643 em `quantity`.
Hélices representa 10,60% dessa quantidade. Portanto, é a categoria líder, mas
não uma maioria do consumo; “concentra” não deve ser comunicado como domínio
absoluto.

## 8. Estratégia e resultados dos testes

### Validações da fonte

- IDs relevantes únicos e não nulos;
- zero referências órfãs na cadeia de joins;
- zero `category_id` nulo;
- `quantity` entre 1 e 10, sem zero ou negativo;
- todos os 2.000 clientes possuem pedidos;
- 1.971 clientes atendem ao corte de diversidade;
- décimo primeiro colocado distinto do décimo, sem empate na fronteira;
- uma única categoria com quantidade máxima.

### Casos que uma suíte de regressão deveria cobrir

- pedido com vários itens sem duplicar faturamento;
- dois pedidos legítimos com o mesmo `total`;
- vários produtos da mesma categoria contando diversidade uma vez;
- clientes com exatamente 12 e 13 categorias;
- empate exato no ticket usando `customer_id`;
- tickets diferentes que ficam iguais depois de arredondados;
- empate entre categorias líderes;
- pedido sem itens, cliente sem pedidos e chave órfã;
- `total` ou categoria nulos;
- diferença entre todos os status e apenas vendas reconhecidas;
- volume maior avaliado com `EXPLAIN ANALYZE`.

### Verificações executadas

O resultado foi reproduzido de duas formas independentes:

1. agregação direta dos CSVs com `Decimal` para os valores financeiros;
2. execução das duas consultas em um banco SQL temporário carregado com os
   arquivos relevantes.

Ambas retornaram os mesmos dez IDs e a categoria `Hélices`, com quantidade 492.
A segunda verificação usou SQLite apenas como teste lógico. A execução final
deve ocorrer em PostgreSQL, pois esse é o banco definido no desafio e é ele que
comprova integralmente sua sintaxe e tipos `NUMERIC`.

## 9. Autocrítica

A consulta está correta para a regra escrita, mas a regra possui fragilidades:

- inclui pedidos que talvez não representem receita;
- não mede recência nem recorrência ao longo do tempo;
- calcula frequência sem usá-la como critério de fidelidade;
- não define janela temporal;
- o filtro de diversidade elimina apenas 1,45% da base;
- mistura unidades de medida ao somar `quantity`;
- não desconta devoluções;
- depende da unicidade lógica de chaves que o schema ainda não garante por
  constraints.

Outra abordagem seria melhor se a Diretoria quisesse fidelidade real. Nesse
caso, faria sentido definir status válidos, período, número mínimo de compras,
recência, meses ativos e tratamento de devoluções. Isso mudaria o indicador e
deveria ser aprovado como nova regra, não introduzido escondido nesta consulta.

Melhorias que podem valer a pena depois:

- formalizar o conceito de receita reconhecida;
- transformar frequência em critério efetivo;
- usar uma janela móvel, como os últimos 12 meses;
- medir participação por receita além de quantidade;
- criar PKs/FKs ou testes automáticos de integridade;
- materializar métricas se o dashboard se tornar recorrente.

Não valem a complexidade nesta entrega:

- clustering de clientes;
- score RFM inventado;
- recursão na hierarquia de categorias;
- uma tabela temporária apenas para evitar repetir CTEs;
- otimizações sem `EXPLAIN ANALYZE`;
- arredondamento ou limpeza dos dados na consulta.

## 10. Perguntas que eu deveria conseguir responder

1. **Por que faturamento e diversidade foram agregados separadamente?**  
   Dominar granularidade, cardinalidade de joins e fan-out.

2. **Por que `COUNT(DISTINCT o.id)` não resolveria sozinho?**  
   Ele corrigiria a frequência, mas `SUM(o.total)` continuaria repetido.

3. **Por que não usar `SUM(DISTINCT o.total)`?**  
   Pedidos diferentes podem ter o mesmo valor e seriam eliminados da soma.

4. **Por que a consulta passa por `product_variants`?**  
   O item referencia a variante; somente ela leva ao produto e à categoria.

5. **Por que `COUNT(DISTINCT category_id)`?**  
   Diversidade significa categorias únicas, não quantidade de produtos ou
   linhas.

6. **Por que todos os status foram considerados?**  
   A especificação não define receita válida por status. Excluir registros
   seria inventar uma regra que muda materialmente o resultado.

7. **Por que ordenar antes de arredondar?**  
   Arredondamento é apresentação e pode criar empates artificiais.

8. **Esse ranking realmente mede fidelidade?**  
   Parcialmente. Mede ticket e amplitude de categorias, mas não exige recência,
   frequência mínima ou recorrência temporal.

9. **O corte de 13 categorias identifica uma elite?**  
   Pouco nesta base: 98,55% dos clientes passam.

10. **É correto somar litros, metros, peças e unidades?**  
    É o cálculo obrigatório, mas a interpretação física é limitada. Uma métrica
    por faturamento ou por unidade de medida poderia ser uma análise adicional.

11. **Por que não foram usados pagamentos ou devoluções?**  
    Porque a fórmula obrigatória aponta `orders.total` e não define ajuste por
    recebimento ou retorno.

12. **Como a consulta trata empate na categoria?**  
    `DENSE_RANK() = 1` devolve todas as categorias com a quantidade máxima.

13. **Como a consulta escalaria?**  
    Avaliar o plano, as chaves de join e os índices com `EXPLAIN ANALYZE`; se o
    uso for recorrente, considerar um mart materializado.

14. **Qual decisão precisa ser validada primeiro com a Diretoria?**  
    Quais status e quais ajustes representam faturamento reconhecido.
