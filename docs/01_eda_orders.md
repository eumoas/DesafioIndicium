# Questão 1 — EDA da tabela `orders`

## Decisão executiva

A tabela é **adequada para exploração descritiva inicial, com ressalvas**, mas ainda não está certificada para decisões financeiras ou operacionais. Os campos centrais desta questão, `created_at` e `total`, estão completos e agregáveis; também há bons sinais de consistência interna. Entretanto, faltam definições de negócio para status elegíveis, moeda, data de corte e semântica dos timestamps. Os valores extremos devem ser investigados, não removidos automaticamente.

## 1. Entendimento do problema

Em outras palavras, a tarefa pede uma primeira auditoria da tabela bruta `orders`: medir cobertura e valores básicos, sem corrigir, excluir ou imputar registros, e então dizer até onde esses dados podem ser considerados confiáveis.

### Requisitos explícitos

- utilizar somente `orders`;
- não limpar nem tratar os dados;
- contar todas as linhas;
- obter o menor e o maior `created_at`;
- calcular mínimo, máximo e média de `total`;
- comentar possíveis outliers, nulos, inconsistências e prontidão para análises;
- entregar o código em SQL.

### Requisitos inferidos

- `COUNT(*)` deve ser usado para contar linhas, pois `COUNT(coluna)` ignora nulos;
- nenhuma linha deve ser filtrada por `status`, mesmo que `draft` e `cancelled` não representem receita realizada;
- o diagnóstico sobre qualidade precisa de consultas auxiliares; mínimo, máximo e média, isoladamente, não sustentam essa conclusão;
- observar nulos, quartis e consistência não é “limpar”: nenhum dado é alterado, imputado ou descartado;
- a conclusão deve se limitar à confiabilidade interna de `orders`, sem prometer reconciliação com itens, pagamentos ou notas fiscais.

### Ambiguidades que mudam a solução

| Lacuna | Impacto |
|---|---|
| Dialeto SQL não informado | A consulta principal é portátil, mas percentis e ingestão variam por banco. |
| Schema de `orders` não fornecido | `total` precisa ser numérico e `created_at` temporal; se forem texto, agregações podem falhar ou produzir coerções silenciosas. |
| Regra de importação de campos vazios não informada | O CSV contém campos vazios em `salesperson_id`; o resultado de nulidade depende de eles terem sido carregados como `NULL`. |
| Moeda e faixa plausível não informadas | Não é possível chamar um total alto de inválido apenas pela magnitude. |
| Semântica de `total` não informada | Não se sabe se representa valor pedido, faturado, pago ou líquido de devoluções. |
| Critério de outlier não informado | IQR é apenas uma regra exploratória, não uma regra de negócio. |
| Data de extração e fuso não informados | O máximo em 2026-12-31 não pode ser julgado corretamente como futuro sem um `as of` oficial. |
| Significado dos timestamps não documentado | Não se sabe se `created_at` é a melhor data para uma futura análise de vendas, embora seja a coluna exigida aqui. |

## 2. Premissas e hipóteses

| Premissa ingênua | Questionamento | Hipótese necessária |
|---|---|---|
| Cada linha é um pedido único | Há duplicidade de `id` ou `order_number`? | Esses campos são identificadores únicos segundo o contrato de dados. |
| Todo pedido é venda realizada | Há `draft` e `cancelled` na tabela. | O objetivo desta EDA é descrever a base bruta, não receita reconhecida. |
| `total` é receita em reais | O enunciado não define moeda nem reconhecimento. | Para KPIs financeiros, moeda e regra contábil precisam ser confirmadas. |
| O maior `total` é erro | Varejo náutico pode ter pedidos legitimamente caros. | Só regras de preço, itens e limites de negócio podem confirmar erro. |
| Vendedor nulo é dado ruim | A ausência pode ser estrutural no e-commerce. | A obrigatoriedade depende do canal e da regra operacional. |
| IDs devem ser contínuos | Sequências podem ter lacunas por rollback ou exclusão. | Continuidade só pode ser exigida se houver contrato explícito. |
| A média representa um pedido típico | A distribuição tem cauda superior e a média supera a mediana. | Mediana e percentis devem contextualizar a média. |
| `created_at` é a data do pedido | Existe também `placed_at`. | A tarefa exige `created_at`; análises posteriores precisam escolher a data pelo significado de negócio. |
| Consistência interna prova confiabilidade | A tabela pode ser internamente coerente e divergir de pagamentos ou itens. | Certificação ampla exige reconciliação, proibida nesta etapa. |

## 3. O que não está óbvio

### Evidências encontradas

| Sinal | Resultado | Interpretação responsável |
|---|---:|---|
| Linhas | 48.998 | Não inferir 50.000 pelo maior ID. |
| Nulos em `total` / `created_at` | 0 / 0 | A média usa todas as 48.998 linhas. |
| Ausências em `salesperson_id` | 24.131 (49,25%) | São campos vazios no CSV; após carga tipada, espera-se `NULL`. Todas ocorrem em `ecommerce`, o que sugere regra estrutural a confirmar. |
| Duplicidades de `id` / `order_number` | 0 / 0 | Bom sinal de unicidade observada, não substitui uma constraint futura. |
| Lacunas no intervalo de IDs 1–50.000 | 1.002 | Sinal de investigação, não prova de registros perdidos. |
| `subtotal - discount_amount` versus `total` | 0 divergências de pelo menos um centavo | Boa coerência interna, ainda dependente da regra de negócio. |
| Valores negativos ou zero em `total` | 0 | Não prova que todos os valores positivos sejam plausíveis. |
| `placed_at = created_at = updated_at` | 48.998 linhas | Pode significar ausência de atualizações, baixa qualidade da linhagem temporal ou dado sintético. |
| Candidatos a outlier por 1,5 × IQR | 452 (0,92%) | São valores raros; não há evidência para removê-los. |

Na data desta análise, 2026-08-16, o maior `created_at` ainda está no futuro. Como o enunciado informa cobertura até 2026, mas não fornece data de extração, esse fato deve virar uma pergunta ao responsável pelo dado, não uma correção automática.

### Casos-limite e falhas silenciosas

- tabela vazia faz `MIN`, `MAX` e `AVG` retornarem `NULL`;
- `AVG(total)` ignora nulos silenciosamente, por isso o denominador é auditado;
- `MIN` e `MAX` sobre texto podem usar ordem lexicográfica;
- inferência automática pode carregar valores monetários como ponto flutuante e gerar diferenças binárias;
- campos vazios do CSV podem virar `NULL`, texto vazio ou erro, dependendo do carregador;
- pedidos inseridos enquanto consultas separadas rodam podem produzir snapshots diferentes; isso não afeta o CSV estático, mas importaria em produção;
- percentis exatos exigem ordenação, com custo aproximado de `O(n log n)`; para 48.998 linhas é irrelevante, para bilhões de linhas não seria;
- expor linhas detalhadas em um dashboard aumentaria risco de uso indevido de identificadores de clientes; esta entrega usa apenas agregados.

## 4. Alternativas consideradas

### Abordagem A — Uma consulta literal

Executar somente `COUNT`, `MIN`, `MAX` e `AVG`.

- **Quando faz sentido:** resposta mínima ou prova rápida.
- **Vantagens:** simples, portátil e barata.
- **Desvantagens:** não sustenta o diagnóstico solicitado sobre nulos, inconsistências e outliers.
- **Complexidade:** `O(n)` e uma varredura.
- **Risco:** concluir que os dados são confiáveis com evidência insuficiente.
- **Sacrifício:** profundidade e capacidade de defesa.

### Abordagem B — Consulta obrigatória + perfil focado (escolhida)

Separar as métricas pedidas de checks de completude, coerência, unicidade e distribuição.

- **Quando faz sentido:** exatamente neste desafio, em uma tabela pequena e estática.
- **Vantagens:** rastreabilidade, clareza e diagnóstico proporcional ao problema.
- **Desvantagens:** algumas funções de percentil dependem do dialeto; são feitas mais varreduras.
- **Complexidade:** agregações `O(n)` e percentil `O(n log n)`.
- **Risco:** tratar hipóteses de negócio como regras confirmadas; os aliases e comentários deixam essa distinção explícita.
- **Sacrifício:** um pouco de concisão e portabilidade em troca de evidência.

### Abordagem C — Framework automatizado de qualidade

Introduzir dbt, Great Expectations ou uma camada genérica de profiling.

- **Quando faz sentido:** pipeline recorrente, múltiplas tabelas e regras já acordadas.
- **Vantagens:** automação, histórico e alertas.
- **Desvantagens:** infraestrutura, dependências e abstrações que não ajudam a responder esta questão.
- **Complexidade:** muito superior ao problema atual.
- **Risco:** demonstrar ferramenta em vez de julgamento técnico.
- **Sacrifício:** simplicidade e tempo de análise.

## 5. Olhar de avaliador

Uma resposta apenas correta entrega os seis agregados. Uma resposta madura explica por que eles não bastam para certificar a tabela, mede as limitações e evita “corrigir” o que ainda não foi provado como erro.

Erros prováveis de um candidato mediano:

- contar pedidos pelo maior `id`;
- usar `COUNT(id)` como sinônimo de quantidade de linhas;
- filtrar somente `paid` sem autorização;
- chamar todo valor extremo de erro e removê-lo;
- declarar `salesperson_id` corrompido sem observar sua relação com `channel`;
- usar `FLOAT` para valores monetários;
- confundir consistência interna com reconciliação financeira;
- introduzir Spark, arquitetura medalhão ou ML para uma tabela de 49 mil linhas.

Decisões que demonstram maturidade:

- manter a consulta obrigatória sem filtros;
- separar cálculo, diagnóstico e regra de negócio;
- preservar a precisão da média no cálculo e arredondar apenas na apresentação;
- classificar outliers como candidatos;
- declarar o dialeto e as hipóteses de tipos;
- dar uma resposta de confiabilidade condicional, não uma garantia absoluta.

## 6. Design thinking, arquitetura e decisões

O design thinking foi aplicado de forma pragmática, sem inventar personas além do enunciado:

| Etapa | Aplicação |
|---|---|
| Empatizar | Sr. Almir precisa de uma conclusão simples; Marina precisa entender o impacto no negócio; Gabriel precisa rastrear cada afirmação até o SQL. |
| Definir | A pergunta real é “confiável para qual uso, com quais ressalvas?”, limitada à tabela `orders`. |
| Idear | Foram comparadas uma resposta literal, um perfil focado e um framework automatizado. |
| Prototipar | A entrega foi dividida em resultado executivo e script SQL reproduzível. |
| Testar | Cada conclusão foi confrontada com nulos, duplicidades, coerência aritmética, distribuição e limitações semânticas. |

A estrutura escolhida é deliberadamente pequena:

1. `orders` permanece como fonte bruta e somente leitura;
2. uma consulta sem filtros produz todas as métricas obrigatórias no mesmo snapshot;
3. consultas independentes produzem evidências de qualidade sem alterar os dados;
4. o relatório traduz evidências em decisão, ressalvas e próximo passo.

O SQL obrigatório usa construções amplamente portáveis. O check de IQR usa `PERCENTILE_CONT`, documentado no script como dependência de dialeto. Não foi incluída ingestão porque o enunciado fala em uma tabela já disponível e não define banco; inventar uma carga seria assumir tipos e ferramenta além do pedido.

## 7. Implementação e resultados

O script executável está em [`sql/01_eda_orders.sql`](../sql/01_eda_orders.sql).

### Partes 1 e 2

| Métrica | Resultado |
|---|---:|
| Quantidade total de linhas | 48.998 |
| Menor `created_at` | 2020-01-01 01:19:28 |
| Maior `created_at` | 2026-12-31 23:43:09 |
| Menor `total` | 32,62 |
| Maior `total` | 127.262,02 |
| Média de `total` | 28.704,992077… |

Para comunicação, a média pode ser exibida como **28.704,99**, preservando-se o valor não arredondado no resultado técnico. Não se usa `R$` porque a moeda não foi documentada.

### Distribuição de `total`

| Métrica | Resultado |
|---|---:|
| Q1 | 13.171,2350 |
| Mediana | 25.917,8400 |
| Q3 | 40.941,8825 |
| Limite inferior de Tukey | -28.484,73625 |
| Limite superior de Tukey | 82.597,85375 |
| Candidatos a outlier | 452 de 48.998 (0,92%) |

### Parte 3 — resposta pronta para entrega

> A tabela `orders` apresenta boa completude nos campos centrais desta análise: não foram observados nulos em `created_at` ou `total`, e as 48.998 linhas participaram do cálculo da média. O intervalo de `total` é amplo, de 32,62 a 127.262,02. Pelo critério exploratório de 1,5 vezes o intervalo interquartil, 452 registros (0,92%) são candidatos a outlier superior; isso indica valores que merecem investigação, mas não autoriza classificá-los como erros ou removê-los sem regras de negócio e detalhamento dos itens.
>
> Também não foram observadas duplicidades em `id` ou `order_number`, valores de `total` negativos ou zerados, nem divergências de pelo menos um centavo na relação observada `subtotal - discount_amount = total`. O único campo com ausência é `salesperson_id`, em 24.131 registros, todos do canal `ecommerce`; esse padrão pode ser estrutural e deve ser validado com a área responsável. A igualdade entre `placed_at`, `created_at` e `updated_at` em todas as linhas, além da ausência de data de extração, limita análises de ciclo de vida e exige esclarecimento.
>
> Portanto, considero a tabela adequada para EDA inicial, mas não pronta de forma irrestrita para KPIs financeiros ou decisões da campanha. Antes dessas análises, devem ser confirmados a moeda, a semântica de `total`, os status elegíveis, a regra de vendedor por canal, a data de corte e a confiabilidade dos timestamps. Não há evidência suficiente para limpar ou excluir os outliers automaticamente.

## 8. Estratégia de testes

### Validação sobre o arquivo recebido

- reconciliar `COUNT(*)` com as 48.998 linhas de dados do CSV, excluindo apenas o cabeçalho;
- confirmar que `COUNT(total) = COUNT(*)` antes de interpretar a média;
- validar que a consulta principal não possui `WHERE` nem `JOIN`;
- conferir unicidade separadamente de continuidade dos IDs;
- comparar a composição de `total` com tolerância explícita de um centavo;
- executar os checks sem qualquer `UPDATE`, `DELETE`, imputação ou descarte.

### Casos que a consulta deve suportar

| Cenário | Comportamento esperado |
|---|---|
| Tabela vazia | Contagem 0; mínimos, máximos e média `NULL`; diagnóstico deve impedir conclusão. |
| `total` todo nulo | `COUNT(*)` preservado, `COUNT(total) = 0` e média `NULL`. |
| Uma única linha | IQR zero; o método de outlier precisa ser interpretado com cautela. |
| Total zero ou negativo | Registro contado e sinalizado, nunca excluído silenciosamente. |
| Duplicidade de identificador | Contagem total preservada e grupo duplicado reportado. |
| Data nula | Intervalo calculado sobre menos linhas e nulidade explicitada. |
| Data futura | Comparação apenas contra uma data de corte acordada. |
| `total` carregado como texto | Falhar cedo ou corrigir o schema de ingestão; não aceitar coerção silenciosa. |
| IQR igual a zero | Evitar concluir automaticamente que todo valor diferente é erro. |
| Tabela sendo atualizada | Executar as consultas em um snapshot/transação consistente. |
| Escala muito maior | Considerar perfil incremental e percentis aproximados. |

## 9. Autocrítica

Esta abordagem pode falhar se os tipos da tabela não forem os assumidos ou se campos vazios não tiverem sido carregados como `NULL`. Ela também usa uma regra estatística genérica: o fator 1,5 do IQR não conhece preços náuticos, mix de produtos, sazonalidade ou múltiplas moedas.

Outra abordagem seria melhor se:

- a fonte fosse atualizada continuamente, exigindo snapshot transacional e monitoramento;
- houvesse bilhões de linhas, tornando percentis exatos caros;
- o objetivo fosse receita reconhecida, exigindo outras tabelas e regras de status;
- arquivos malformados precisassem de uma camada raw textual com quarentena de rejeições;
- as regras fossem recorrentes, justificando testes automatizados.

Melhorias úteis depois da confirmação de escopo:

- documentar um contrato de dados e tipos;
- parametrizar data de corte e timezone;
- definir moeda e status que representam venda;
- reconciliar total com itens, pagamentos, notas e devoluções em tarefas que permitam outras tabelas;
- transformar checks confirmados em testes automatizados.

Melhorias que **não** valem a complexidade agora:

- remover ou winsorizar outliers;
- criar classes ou funções genéricas para seis agregações;
- adicionar Spark, orquestrador ou data lake;
- treinar detector de anomalias sem rótulos e regras de negócio;
- criar índices para agregações integrais em apenas 48.998 linhas.

## 10. Perguntas que eu deveria conseguir responder

1. **Por que usar `COUNT(*)` e não `COUNT(id)`?**  
   Dominar a semântica de nulos nas funções de agregação.

2. **Qual é o denominador real de `AVG(total)`?**  
   Entender que `AVG` ignora `NULL` e deve ser contextualizado por `COUNT(total)`.

3. **Por que `draft` e `cancelled` entram nos números?**  
   Separar fidelidade à EDA bruta de uma definição posterior de receita.

4. **Por que o maior valor não foi removido?**  
   Distinguir valor extremo, anomalia estatística e erro confirmado pelo negócio.

5. **Por que usar IQR em vez de z-score?**  
   Explicar robustez à assimetria e reconhecer que o fator 1,5 continua sendo uma convenção.

6. **Por que usar decimal exato para dinheiro?**  
   Dominar representação binária, arredondamento e precisão monetária.

7. **Casting na ingestão é limpeza?**  
   Explicar a diferença entre interpretar o schema e corrigir, imputar ou descartar valores.

8. **Os 1.002 IDs ausentes provam perda de dados?**  
   Entender sequências, rollbacks, exclusões e limites de inferência.

9. **Os 24.131 vendedores ausentes representam má qualidade?**  
   Avaliar nulidade condicional por canal e exigir contrato de dados.

10. **Como avaliar datas posteriores à data atual?**  
    Exigir timestamp de extração, timezone e contexto do snapshot.

11. **O que a tabela isolada não permite validar?**  
    Referencialidade, composição do pedido, faturamento, pagamento e receita reconhecida.

12. **Por que uma única consulta para as métricas obrigatórias?**  
    Reduzir varreduras e produzir resultados no mesmo snapshot.

13. **Como a solução mudaria em escala muito maior?**  
    Dominar particionamento, agregações incrementais, amostragem e percentis aproximados.

14. **Qual evidência permitiria declarar um total alto inválido?**  
    Relacionar regras de preço, itens, quantidades, moeda, impostos, frete e limites aprovados.

15. **Por que a conclusão é condicional?**  
    Diferenciar ausência de evidência de erro de evidência de ausência de erro.
