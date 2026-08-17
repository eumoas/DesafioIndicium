# Questão 6 — Previsão mensal de demanda

## Decisão executiva

Foi construído um baseline de média móvel de três meses para o produto com nome
exato `Bússola de Bordo 702`. A avaliação usa o protocolo *walk-forward*: cada
mês é previsto no seu início usando somente os três meses reais já encerrados.

| Mês previsto | Meses usados | Previsão | Real | Erro absoluto |
|---|---|---:|---:|---:|
| Janeiro/2026 | out/2025, nov/2025 e dez/2025 | 38,67 | 79 | 40,33 |
| Fevereiro/2026 | nov/2025, dez/2025 e jan/2026 | 53,67 | 68 | 14,33 |
| Março/2026 | dez/2025, jan/2026 e fev/2026 | 56,33 | 60 | 3,67 |

O **MAE foi de 19,44 unidades por mês**. As previsões somaram 148,67 unidades,
enquanto o realizado foi de 207 unidades. Portanto, o baseline subestimou o
trimestre em 58,33 unidades, ou 28,18% do total observado.

Resposta objetiva:

- **a. O baseline é adequado?** É adequado como referência inicial simples e
  auditável, mas não como modelo final para decidir compras. Ele subestimou os
  três meses e errou janeiro em aproximadamente 40 unidades.
- **b. Limitação principal:** vendas registradas não representam necessariamente
  a demanda quando há ruptura de estoque. Sem um histórico de disponibilidade,
  o modelo pode aprender uma demanda censurada e continuar comprando menos do
  que o necessário. Além disso, a média móvel não modela sazonalidade.

## 1. Entendimento do problema

O objetivo técnico é transformar quatro fontes no grão de item de pedido em uma
série mensal de unidades vendidas, separar treino e teste por tempo, gerar um
baseline que não consulte o futuro e medir seu erro no primeiro trimestre de
2026.

### Requisitos explícitos

- relacionar `products`, `product_variants`, `order_items` e `orders`;
- considerar somente o produto `Bússola de Bordo 702`;
- utilizar no treino os dados disponíveis até 31/12/2025;
- reservar janeiro a março de 2026 para teste;
- agregar as vendas por mês;
- prever com a média das vendas dos três meses anteriores;
- calcular o MAE entre previsão e realizado;
- avaliar objetivamente a adequação e uma limitação do método.

### Requisitos inferidos

- `orders.placed_at` representa a data da venda;
- a variável prevista é `SUM(order_items.quantity)`, e não quantidade de pedidos
  ou faturamento;
- a busca do produto deve usar igualdade exata;
- meses sem itens precisam existir na série com valor zero;
- a separação deve ser temporal, nunca aleatória;
- previsões não devem ser arredondadas antes do MAE;
- dados posteriores a março de 2026 não podem participar da modelagem;
- cada previsão mensal pode ser atualizada quando o mês anterior terminar.

### Ambiguidades que mudariam o resultado

- o nome do produto corresponde a mais de um cadastro;
- o enunciado não define quais status representam uma venda válida;
- não está explícito se as três previsões são produzidas juntas em 31/12/2025 ou
  atualizadas no início de cada mês;
- não existe um limite de MAE aceitável para o negócio;
- não existem dados de ruptura, estoque disponível, preço, promoção ou prazo de
  fornecedor.

## 2. Premissas e hipóteses

| Premissa ingênua | Risco | Decisão adotada |
|---|---|---|
| O nome identifica um único produto | Selecionar um ID arbitrariamente | Consolidar todos os IDs com nome exatamente igual |
| Uma busca parcial é suficiente | Incluir `Bússola de Bordo 7024` | Usar igualdade exata |
| Contar linhas mede unidades | Cada item pode ter `quantity` maior que um | Somar `quantity` |
| Apenas meses com venda importam | A janela passaria pelos três últimos meses com registro | Criar um calendário mensal e preencher ausências com zero |
| Posso dividir os dados aleatoriamente | O treino enxergaria informações posteriores | Fazer corte temporal |
| A média de janeiro pode usar janeiro | Isso seria vazamento temporal | Calcular antes de adicionar o realizado ao histórico |
| Todo pedido é uma venda concluída | Existem `paid`, `confirmed`, `cancelled` e `draft` | Incluir todos, pois nenhuma regra de status foi fornecida, e registrar a lacuna |
| Previsão é a quantidade final de compra | Faltam estoque atual, lead time e nível de serviço | Tratar a saída como demanda esperada, não como pedido ao fornecedor |

O resultado pressupõe uma atualização mensal. Janeiro real pode participar da
previsão de fevereiro porque, no início de fevereiro, janeiro já é informação
passada. Essa regra seria inválida se todas as previsões precisassem ser
congeladas em 31/12/2025.

## 3. O que não está óbvio

### O nome do produto não é uma chave

Existem dois registros com o nome exato solicitado:

| `product_id` | Variantes |
|---:|---|
| 74 | 147 e 148 |
| 240 | 486 |

Eles pertencem inclusive a categorias e marcas diferentes. Como o enunciado
filtra pelo nome, ambos foram consolidados. Escolher apenas o primeiro registro
seria uma regra inventada. Uma busca parcial também estaria errada porque existe
o produto `Bússola de Bordo 7024`.

Em produção, essa duplicidade deveria ser confirmada com cadastro ou Negócios.
Os campos `created_at` não resolvem a dúvida: há vendas anteriores à criação
registrada dos produtos e variantes, indicando inconsistência temporal na fonte.

### A cadeia de chaves e o grão precisam ser preservados

O relacionamento utilizado foi:

```text
products.id
    -> product_variants.product_id
    -> product_variants.id
    -> order_items.product_variant_id
    -> order_items.order_id
    -> orders.id
```

O dataset unificado permanece no grão de `order_item`. Os joins são validados
como muitos-para-um, impedindo que uma chave duplicada em tabela mestre
multiplique unidades silenciosamente. Depois da união, `quantity` é somada por
mês de `placed_at`.

Para o recorte de treino e teste foram encontrados:

- 407 linhas de itens, em três variantes;
- 365 linhas e 1.966 unidades no treino;
- 42 linhas e 207 unidades no teste;
- 72 meses de treino, de janeiro de 2020 a dezembro de 2025;
- um mês sem venda no histórico, outubro de 2020, preservado como zero.

### A ordem do cálculo evita vazamento temporal

Para cada mês de teste, o programa executa esta sequência:

```text
selecionar os três valores anteriores
        -> calcular a previsão
        -> registrar o erro
        -> adicionar o realizado ao histórico
```

Assim, janeiro usa 34, 60 e 22 unidades de outubro a dezembro. Fevereiro usa
60, 22 e o realizado de janeiro. Março usa 22 e os realizados de janeiro e
fevereiro. Nenhum mês usa seu próprio valor ou um valor futuro.

### O status é uma definição de negócio ausente

O primeiro trimestre contém 19 unidades em pedidos `cancelled` e 6 em `draft`.
Elas foram mantidas porque a tarefa não autoriza um filtro. Considerar somente
`paid`, ou `paid` mais `confirmed`, mudaria o alvo e o MAE.

Uma entrega madura não escolhe silenciosamente o status que produz o melhor
resultado. Marina precisa confirmar o evento que representa venda para o
planejamento de demanda.

### MAE não responde sozinho à decisão de estoque

O MAE atribui o mesmo peso a excesso e falta de uma unidade. No cenário descrito,
o custo de faltar produto pode ser muito diferente do custo de manter estoque.
Também há apenas três observações no teste, número insuficiente para concluir que
o desempenho será estável em outras estações.

Previsões fracionárias são válidas como valores esperados. Arredondar para
unidades inteiras, aplicar estoque de segurança e descontar o estoque disponível
são decisões posteriores, não especificadas no exercício.

## 4. Alternativas consideradas

### A — Média móvel de três meses com atualização mensal (escolhida)

- **Quando faz sentido:** baseline operacional atualizado no início de cada mês.
- **Vantagens:** simples, barato, transparente e solicitado pelo enunciado.
- **Desvantagens:** reage com atraso e ignora padrões anuais.
- **Complexidade:** baixa.
- **Risco:** subestimar mudanças rápidas, como ocorreu em janeiro.
- **Sacrifício:** capacidade de representar sazonalidade e variáveis externas.

### B — Previsão única feita em 31/12/2025

Se os três meses precisassem ser previstos juntos, o realizado de janeiro não
estaria disponível para fevereiro. Há duas políticas simples:

- repetir em cada mês a média de outubro a dezembro: MAE de 30,33;
- usar previsões anteriores recursivamente: previsões de 38,67, 40,22 e 33,63,
  com MAE de 31,49.

Essa alternativa corresponde a outro processo de negócio. Ela sacrifica a
atualização mensal e apresentou erro maior neste trimestre.

### C — Baseline sazonal

Usar o mesmo mês do ano anterior permite representar sazonalidade com pouca
complexidade. Neste teste, seu MAE é 25,00, pior que os 19,44 da média móvel.
Ainda assim, é uma comparação útil antes de adotar modelos mais sofisticados.

### D — Modelo com sazonalidade e variáveis operacionais

Um modelo de séries temporais ou supervisionado faria sentido depois de obter
estoque disponível, rupturas, promoções, preço e prazo de reposição. Ele poderia
reduzir viés, mas exige mais dados, backtests em várias janelas e monitoramento.
Implementá-lo agora não corrigiria a ausência de demanda perdida e fugiria do
baseline solicitado.

## 5. Olhar de avaliador

Uma resposta apenas funcional provavelmente selecionaria o primeiro produto
encontrado, contaria linhas, ignoraria meses zerados ou calcularia a média móvel
incluindo o próprio mês previsto.

Decisões que demonstram maturidade:

- detectar que o nome não é único e não esconder a ambiguidade;
- validar a cardinalidade das chaves antes de agregar;
- usar `quantity` como alvo de unidades;
- construir uma série mensal contínua;
- declarar o instante em que cada previsão é emitida;
- separar treino e teste por datas inclusivas e exclusivas;
- calcular o MAE com valores não arredondados;
- não escolher status sem regra de negócio;
- diferenciar baseline, previsão de demanda e decisão de compra;
- avaliar o erro e o viés, não apenas mostrar que o código executou.

Complexidade desnecessária seria adicionar `scikit-learn`, redes neurais, classes
de modelo, banco de features ou otimização de hiperparâmetros para calcular uma
média de três valores.

## 6. Design thinking, arquitetura e decisões

### Empatizar

- **Gabriel Santos:** recebe funções pequenas, validações de chaves, testes de
  fronteira temporal e uma regra de previsão reproduzível.
- **Marina Costa:** recebe o erro em unidades, o déficit trimestral e as lacunas
  de status, estoque e custo de ruptura.
- **Sr. Almir:** consegue reproduzir cada previsão com três somas e uma divisão,
  sem depender de um algoritmo opaco ou de infraestrutura em nuvem.

### Definir

O problema não é prometer uma quantidade exata. É criar uma primeira referência
mensurável, sem vazamento de futuro, para substituir o *feeling* e permitir que
modelos futuros provem se realmente melhoram a decisão.

### Fluxo da solução

```text
ler e validar os quatro CSVs
             |
filtrar o nome exato e obter todos os IDs
             |
unir produto -> variante -> item -> pedido
             |
somar quantity em calendário mensal contínuo
             |
treino até dez/2025 | teste jan-mar/2026
             |
média móvel walk-forward de três meses
             |
previsões + erros absolutos + MAE
```

Foi utilizado `pandas` somente para leitura, joins, datas e agregação. O MAE e a
média são implementados diretamente, pois uma dependência de modelagem não
agregaria valor a este baseline.

## 7. Implementação

O código está em [`scripts/questao_6_1.py`](../scripts/questao_6_1.py). A dependência
foi registrada em [`requirements.txt`](../requirements.txt).

Execução a partir da raiz do projeto:

```bash
python3 -m pip install -r requirements.txt
python3 scripts/questao_6_1.py data/raw --output-directory outputs
```

As fontes permanecem inalteradas em `data/raw`; os três artefatos gerados são
gravados separadamente em `outputs/`.

O programa gera três arquivos:

- [`outputs/questao_6_dataset_unificado.csv`](../outputs/questao_6_dataset_unificado.csv):
  itens relacionados aos dois produtos, limitados ao período de treino e teste;
- [`outputs/questao_6_vendas_mensais.csv`](../outputs/questao_6_vendas_mensais.csv):
  série mensal completa, incluindo zeros e indicação de treino/teste;
- [`outputs/questao_6_previsoes.csv`](../outputs/questao_6_previsoes.csv):
  previsão, realizado e erro absoluto para os três meses.

O script falha com uma mensagem clara quando faltam arquivos, chaves não são
únicas, datas são inválidas, o produto não existe ou não há histórico suficiente.
Os dados de abril a dezembro de 2026 ficam fora do arquivo de modelagem e dos
cálculos.

## 8. Estratégia de testes

Os testes específicos estão em [`tests/test_forecast.py`](../tests/test_forecast.py).

Foram verificados:

- igualdade exata do nome, incluindo os dois IDs corretos e excluindo o produto
  cujo nome termina em `7024`;
- mês sem venda convertido em zero;
- fronteira de treino em dezembro de 2025;
- teste contendo exatamente janeiro, fevereiro e março de 2026;
- cálculo walk-forward usando somente valores anteriores;
- rejeição de histórico menor que a janela;
- MAE calculado sobre previsões não arredondadas.

Comando executado:

```bash
python3 -m unittest discover -s tests -v
```

Os 30 testes do projeto passaram, sendo seis dedicados a esta questão. O código
também passou nas verificações de estilo do `ruff`.

Em uma evolução, eu acrescentaria testes de CSV malformado, quantidade nula,
chave órfã e alteração dos valores futuros para provar que previsões anteriores
permanecem iguais.

## 9. Autocrítica

O baseline dá peso igual aos três meses e, por isso, responde tarde a mudanças.
Ele também não diferencia sazonalidade, tendência, promoção, preço ou canal. O
erro de janeiro mostra que uma média recente pode ser insuficiente justamente
quando a demanda acelera.

O teste possui apenas três meses. O MAE de 19,44 não deve ser tratado como uma
estimativa estável do erro futuro, e nenhum limite de aceitação foi fornecido.
Uma avaliação mais séria usaria várias janelas históricas de backtest e
compararia o modelo com baselines de último mês, média histórica e sazonal.

A maior limitação não é algorítmica: se o produto ficou sem estoque, a venda
observada é menor que a demanda. Sem dados de disponibilidade e vendas perdidas,
até um modelo sofisticado pode aprender o alvo errado.

Outra abordagem seria melhor se:

- as três previsões fossem exigidas de uma só vez, caso em que o protocolo deve
  ser fixo ou recursivo;
- existisse sazonalidade estável, favorecendo um baseline do mesmo mês do ano
  anterior;
- houvesse histórico de estoque e promoções, permitindo estimar demanda não
  censurada e usar variáveis externas.

Não considero que redes neurais, tuning extensivo, previsão diária ou uma
plataforma de MLOps valham a complexidade neste estágio. Primeiro é necessário
resolver a definição do produto, dos status e do alvo de demanda.

## 10. Perguntas que eu deveria conseguir responder

1. **Por que foram usados dois `product_id`?**  
   Dominar a diferença entre chave técnica e nome de negócio, além do risco de
   selecionar registros arbitrariamente.

2. **Por que a busca é exata?**  
   Saber explicar que uma busca parcial incluiria outro produto, alterando a
   população analisada.

3. **Por que somar `quantity` e não contar pedidos ou itens?**  
   Dominar granularidade e a definição da variável-alvo em unidades.

4. **Como os quatro arquivos se relacionam?**  
   Conseguir percorrer e justificar toda a cadeia de chaves, incluindo a
   cardinalidade de cada join.

5. **Como meses sem venda entram na média móvel?**  
   Explicar por que uma série temporal precisa de calendário contínuo e por que
   ausência de registro corresponde a zero unidades nesse contexto.

6. **Por que janeiro real aparece na previsão de fevereiro?**  
   Dominar *forecast origin*, atualização mensal e validação *walk-forward*.

7. **Isso não é vazamento temporal?**  
   Demonstrar que o realizado só entra depois da previsão do próprio mês e que
   nenhum dado futuro participa.

8. **E se as três previsões forem solicitadas em 31/12/2025?**  
   Explicar a diferença entre previsão de um passo, horizonte fixo e previsão
   recursiva, incluindo a mudança do MAE.

9. **Como o MAE de 19,44 foi calculado e interpretado?**  
   Saber calcular o erro absoluto, preservar casas decimais e traduzi-lo em
   impacto de estoque sem confundi-lo com MAPE.

10. **Por que o baseline não é suficiente para compras?**  
    Dominar viés de subestimação, amostra pequena, custo assimétrico e ausência
    de um limite de erro aceito pelo negócio.

11. **Vendas observadas são iguais à demanda?**  
    Explicar demanda censurada por ruptura de estoque e quais dados seriam
    necessários para estimar vendas perdidas.

12. **Quais status deveriam entrar?**  
    Reconhecer que essa é uma regra de negócio e explicar por que não foi
    inventada silenciosamente.

13. **Como a previsão vira uma ordem de compra?**  
    Dominar estoque disponível, estoque de segurança, lead time, lote mínimo,
    nível de serviço e arredondamento operacional.

14. **Qual seria o próximo experimento?**  
    Propor backtests em várias janelas, baseline sazonal e inclusão de estoque e
    promoções antes de aumentar a complexidade do modelo.
