# Desafio Indicium — LH Nautical

Solução de ponta a ponta para o desafio fictício da LH Nautical, cobrindo
exploração de dados, inferência de schema PostgreSQL, carga transacional,
análises SQL, previsão de demanda, recomendação de produtos e comunicação
executiva por dashboard e PDF.

O repositório prioriza rastreabilidade e interpretação responsável. Os números
publicados seguem literalmente as regras disponíveis, enquanto hipóteses de
negócio não confirmadas permanecem explícitas.

> **Atenção:** os 24 CSVs brutos na raiz contêm dados pessoais e operacionais.
> Eles são necessários para reprodução local, mas **não devem ser publicados**.
> Consulte [Segurança e dados sensíveis](#segurança-e-dados-sensíveis) antes de
> compartilhar ou versionar este projeto.

## Visão do desafio

A LH Nautical representa uma operação de varejo náutico com lojas, armazéns e
e-commerce. O snapshot contém 24 arquivos CSV, 433.424 registros e cobertura
entre 2020 e 2026. A solução percorre duas trilhas complementares:

1. engenharia e análise relacional: inferir o schema, preparar uma carga segura
   no PostgreSQL e responder às questões analíticas em SQL;
2. ciência de dados e comunicação: construir um baseline temporal, um ranking
   de similaridade, um contrato JSON agregado, um dashboard local e um resumo
   executivo em PDF.

A pergunta orientadora é a do Sr. Almir: **“Posso confiar nesses dados para
tomar decisões?”** A resposta desta entrega é condicional: o snapshot apresenta
boa consistência estrutural para exploração, mas status elegíveis, moeda,
reconhecimento do valor e data oficial de corte ainda exigem governança.

## Para quem a solução foi desenhada

| Persona | Necessidade | Como a entrega responde |
|---|---|---|
| **Gabriel Santos, Tech Lead** | Código legível, linhagem, premissas e testes | Scripts pequenos por responsabilidade, SQL comentado, documentação por questão, checks e reprodução local |
| **Marina Costa, Gerente de Negócios** | Sinais comerciais acionáveis e seus riscos | Ranking anonimizado, composição por canal, categorias do grupo elite e recomendação com ressalvas de margem e causalidade |
| **Sr. Almir, Fundador** | Números auditáveis, simples e independentes de nuvem | Calendário explícito, baseline reproduzível, arquivos locais e visão do dashboard dedicada à confiança nos dados |

O dashboard organiza a leitura em quatro perspectivas: **Ponte de Comando**,
**Marina**, **Sr. Almir** e **Gabriel**. O roteiro de apresentação está em
[docs/08_dashboard_e_apresentacao.md](docs/08_dashboard_e_apresentacao.md).

## Resultados centrais — questões 1 a 7

### Q1 — EDA de `orders`

- **48.998 linhas**;
- `created_at` entre **2020-01-01 01:19:28** e
  **2026-12-31 23:43:09**;
- `total` mínimo de **32,62**, máximo de **127.262,02** e média de
  **28.704,992077…**;
- zero nulos em `total` e `created_at`, zero duplicidades observadas em `id` e
  `order_number` e zero divergências de pelo menos um centavo em
  `subtotal - discount_amount = total`;
- **452 pedidos (0,92%)** são candidatos a outlier superior pelo critério de
  1,5 × IQR. Eles foram sinalizados, não removidos.

Conclusão: a tabela serve para EDA inicial, mas não deve sustentar KPIs
financeiros sem confirmar moeda, status válidos, semântica de `total`, corte e
timestamps. Veja [docs/01_eda_orders.md](docs/01_eda_orders.md) e
[sql/01_eda_orders.sql](sql/01_eda_orders.sql).

### Q2 — Inferência do schema PostgreSQL

- os **24 CSVs e 433.424 registros** foram inspecionados integralmente;
- foram gerados **24 `CREATE TABLE`** em um único
  [schema.sql](schema.sql);
- dinheiro e decimais usam `NUMERIC`, códigos sensíveis a zeros à esquerda
  permanecem `TEXT` e timestamps sem offset viram
  `TIMESTAMP WITHOUT TIME ZONE`;
- `stock_levels.reorder_point` está vazio em todas as 6.054 linhas e, por falta
  de evidência, recebeu o fallback `TEXT` com aviso;
- PKs, FKs, `NOT NULL`, enums e limites `VARCHAR(n)` não foram inventados a
  partir de um único snapshot.

Implementação e justificativas:
[scripts/schema.py](scripts/schema.py) e
[docs/02_schema.md](docs/02_schema.md).

### Q3 — Carga no PostgreSQL

O carregador em [scripts/load.py](scripts/load.py) prepara a ingestão dos 24
arquivos por `COPY FROM STDIN`, dentro de uma única transação. Antes de inserir,
ele valida estrutura CSV, catálogo, ordem das colunas e estado das tabelas; ao
final, reconcilia as contagens. Por padrão, tabelas não vazias cancelam a
execução. `--replace` é uma opção explícita e transacional, não o comportamento
padrão.

A pré-validação local encontrou **24 fontes, 433.424 registros e cerca de
37 MB**. Os testes unitários cobrem a orquestração e rollback com conexões
simuladas. **A carga não foi executada contra uma instância PostgreSQL real
neste ambiente**; esse teste de integração continua pendente e não é tratado
como concluído. Detalhes em [docs/03_carregamento.md](docs/03_carregamento.md).

### Q4 — Clientes com ticket alto e diversidade

- os valores de pedido foram agregados antes do relacionamento com itens,
  evitando multiplicação por *fan-out*;
- **1.971 de 2.000 clientes (98,55%)** atendem ao corte de pelo menos 13
  categorias diretas;
- o primeiro cliente anonimizado do ranking possui 26 pedidos, valor acumulado
  registrado de **1.087.838,44**, ticket médio de **41.839,94** e diversidade
  de 14 categorias;
- os dez selecionados somam 225 pedidos, 792 linhas de item e 4.643 em
  `quantity`;
- **Hélices** é a categoria líder, com **492** em `quantity` (10,60% do grupo).

O corte elimina apenas 1,45% da base e, portanto, é pouco seletivo; na prática,
o ticket médio domina o ranking. Veja
[sql/questao_4.sql](sql/questao_4.sql) e
[docs/04_analise_clientes.md](docs/04_analise_clientes.md).

### Q5 — Calendário completo e média POS

Foi construído um calendário inclusivo de **2.557 dias**, de 2020-01-01 a
2026-12-31. Pedidos POS são somados no grão diário e relacionados ao calendário
por `LEFT JOIN`; os 78 dias sem registro POS entram como zero antes da média.

- **Quinta-feira** tem a menor média diária: **157.154,32**;
- Domingo vem em seguida, com **157.616,13**;
- a diferença é de apenas **461,81**, aproximadamente 0,29%;
- o recorte contém 14.656 pedidos POS e 419.273.315,30 na soma de
  `orders.total`.

O resultado descreve a rede agregada e não sustenta, sozinho, fechamento de
loja. Consulte [sql/questao_5.sql](sql/questao_5.sql) e
[docs/05_dimensao_calendario.md](docs/05_dimensao_calendario.md).

### Q6 — Baseline de previsão de demanda

Para o nome exato `Bússola de Bordo 702`, dois cadastros de produto foram
consolidados. A série mensal contínua inclui meses zerados, treina até dezembro
de 2025 e usa janeiro a março de 2026 como teste *walk-forward*.

| Mês | Previsão | Realizado | Erro absoluto |
|---|---:|---:|---:|
| 2026-01 | 38,67 | 79 | 40,33 |
| 2026-02 | 53,67 | 68 | 14,33 |
| 2026-03 | 56,33 | 60 | 3,67 |

O **MAE foi 19,44 unidades/mês**. O baseline previu 148,67 unidades diante de
207 realizadas e subestimou o trimestre em **58,33 unidades**. Ele é uma
referência auditável, não uma ordem de compra. Veja
[scripts/questao_6_1.py](scripts/questao_6_1.py),
[docs/06_previsao_demanda.md](docs/06_previsao_demanda.md) e
[outputs/questao_6_previsoes.csv](outputs/questao_6_previsoes.csv).

### Q7 — Recomendação por compras em comum

O modelo cria interações binárias cliente-produto: uma compra repetida continua
valendo uma interação. A similaridade do cosseno é calculada entre vetores de
clientes, considerando todos os status.

Para `Motor de Popa 1949`, comprado por **397 clientes**, o top 5 foi:

| Posição | Produto | Similaridade | Clientes em comum |
|---:|---|---:|---:|
| 1 | Motor de Popa 5331 | 0,25655258 | 106 |
| 2 | Cabo Náutico 2105 | 0,25623873 | 103 |
| 3 | Vela Mestra 1913 | 0,25578459 | 100 |
| 4 | Cabo Náutico 9048 | 0,23933230 | 99 |
| 5 | GPS Plotter 6249 | 0,23774366 | 98 |

O ranking mede afinidade de público, não complementaridade causal nem
probabilidade individual de compra. Consulte
[scripts/questao_7_1.py](scripts/questao_7_1.py) e
[outputs/questao_7_top_5.csv](outputs/questao_7_top_5.csv).

## Premissas críticas

Estas premissas devem acompanhar qualquer apresentação dos resultados:

- **Todos os status entram literalmente:** `paid`, `confirmed`, `cancelled` e
  `draft`. Nenhuma questão forneceu uma definição aprovada de venda elegível.
- **Valor registrado não é receita reconhecida:** a soma de `orders.total` não
  desconta automaticamente cancelamentos, rascunhos, devoluções ou diferenças
  de pagamento e nota fiscal. Também não representa lucro, margem ou caixa.
- **Moeda é uma premissa de apresentação:** `orders` não possui coluna de
  moeda. Dashboard e PDF exibem BRL/R$ pelo contexto da operação brasileira,
  mas a unidade precisa ser confirmada pelo responsável pelo dado.
- **O snapshot chega a 2026-12-31:** há registros posteriores à data de geração
  da entrega, 2026-08-16. A data máxima representa cobertura do arquivo, não um
  estado operacional corrente confirmado.
- **Q4 usa categorias diretas:** o corte é de pelo menos 13 e a soma de
  `quantity` mistura unidades como UN, PC, M e L.
- **Q5 usa `placed_at` e `channel = 'pos'`:** a análise é da rede inteira, não
  de cada loja.
- **Q6 é atualizado mês a mês:** o realizado de janeiro pode entrar na previsão
  de fevereiro; uma previsão congelada em 31/12/2025 seria outro protocolo.
- **Q7 usa presença binária:** frequência e quantidade não aumentam a
  interação cliente-produto.

## Arquitetura e fluxo de dados

```text
24 CSVs brutos
    |
    +-- scripts/schema.py --> schema.sql
    |                           |
    |                           +-- scripts/load.py --> PostgreSQL
    |                                                    |
    |                                                    +-- SQL Q1, Q4 e Q5
    |
    +-- pandas --> Q6 / Q7 / scripts/build_dashboard_data.py
                                      |
                                      +-- dashboard/public/data/dashboard.json
                                                        |
                                                        +-- Dashboard React
                                                        +-- PDF executivo
```

O PostgreSQL é a trilha relacional prevista para as questões SQL. O dashboard e
o PDF usam um caminho local separado, recalculado dos CSVs com pandas, para não
depender de uma instância de banco durante a apresentação.

### Árvore do repositório

```text
.
├── *.csv                              # 24 fontes brutas; não publicar
├── Enunciado.md                       # contexto recebido
├── docs/                              # decisões, resultados e autocrítica
│   ├── 01_eda_orders.md
│   ├── 02_schema.md
│   ├── 03_carregamento.md
│   ├── 04_analise_clientes.md
│   ├── 05_dimensao_calendario.md
│   ├── 06_previsao_demanda.md
│   └── 08_dashboard_e_apresentacao.md
├── sql/                               # consultas das questões 1, 4 e 5
├── scripts/
│   ├── schema.py                      # inferência do DDL
│   ├── load.py                        # carga PostgreSQL
│   ├── questao_6_1.py                 # previsão
│   ├── questao_7_1.py                 # recomendação
│   ├── build_dashboard_data.py        # contrato agregado sem PII
│   └── generate_executive_report.py   # PDF executivo
├── tests/                             # 41 testes unitários/integração local
├── outputs/                           # resultados técnicos de Q6 e Q7
├── dashboard/                         # React, TypeScript, Tailwind e Recharts
│   ├── public/data/dashboard.json
│   └── src/
├── deliverables/
│   └── LH_Nautical_Resumo_Executivo.pdf
├── requirements.txt
└── schema.sql
```

`dashboard/node_modules` e `dashboard/dist` são artefatos locais de instalação
e build; não fazem parte da arquitetura lógica.

## Como reproduzir

Execute os comandos a partir da raiz do repositório, salvo quando indicado.

### 1. Preparar o ambiente Python

Requisitos: Python 3 e, para a trilha de banco, PostgreSQL com o cliente `psql`.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

As dependências declaradas são pandas, psycopg2-binary e ReportLab.

### 2. Gerar o schema

```bash
python3 scripts/schema.py . -o schema.sql
```

Saída esperada para este snapshot: 24 tabelas e 433.424 registros analisados,
com um aviso para `stock_levels.reorder_point`.

### 3. Aplicar o schema e carregar o PostgreSQL

Defina a conexão somente no ambiente; não grave credenciais no repositório:

```bash
export LH_NAUTICAL_DATABASE_URL='postgresql://USUARIO:SENHA@HOST:5432/BANCO'
psql "$LH_NAUTICAL_DATABASE_URL" -v ON_ERROR_STOP=1 -f schema.sql
python3 scripts/load.py .
```

O carregador também aceita variáveis padrão `PG*` e `--db-schema`. Evite
`--dsn` com senha na linha de comando, pois ela pode aparecer no histórico e na
lista de processos. Use `--replace` apenas quando a substituição integral do
snapshot for deliberada.

### 4. Executar as análises SQL

Depois da carga:

```bash
psql "$LH_NAUTICAL_DATABASE_URL" -v ON_ERROR_STOP=1 -f sql/01_eda_orders.sql
psql "$LH_NAUTICAL_DATABASE_URL" -v ON_ERROR_STOP=1 -f sql/questao_4.sql
psql "$LH_NAUTICAL_DATABASE_URL" -v ON_ERROR_STOP=1 -f sql/questao_5.sql
```

### 5. Recalcular previsão e recomendação

```bash
python3 scripts/questao_6_1.py .
python3 scripts/questao_7_1.py .
```

Esses comandos atualizam os arquivos técnicos em [outputs/](outputs/).

### 6. Regenerar dados do dashboard e PDF

O JSON deve ser atualizado antes do PDF:

```bash
python3 scripts/build_dashboard_data.py .
python3 scripts/generate_executive_report.py
```

Saídas:

- [dashboard/public/data/dashboard.json](dashboard/public/data/dashboard.json);
- [deliverables/LH_Nautical_Resumo_Executivo.pdf](deliverables/LH_Nautical_Resumo_Executivo.pdf).

### 7. Executar o dashboard localmente

Requisito documentado: Node.js 20.19 ou superior.

```bash
cd dashboard
npm install
npm run typecheck
npm run build
npm run dev
```

O Vite informa no terminal o endereço **local** da sessão. Para conferir o
build estático, permaneça em `dashboard/`, encerre o servidor de desenvolvimento
e execute:

```bash
npm run preview
```

Não há URL pública ou implantação externa declarada neste repositório.

### 8. Executar os testes Python

```bash
python3 -m unittest discover -s tests -v
```

Resultado observado nesta entrega: **41 testes aprovados**.

| Área | Testes | Cobertura principal |
|---|---:|---|
| Inferência de schema | 12 | Tipos, promoções, CSVs inválidos, Unicode, escrita determinística e atômica |
| Carga PostgreSQL | 12 | Pré-validação, SQL seguro, preservação do CSV, transação e falhas simuladas |
| Previsão | 6 | Nome exato, calendário mensal, corte temporal, walk-forward e MAE |
| Recomendação | 4 | Interação binária, cosseno, desempate e alvo sem compradores |
| Dados do dashboard | 7 | Schema JSON, números centrais, status, privacidade e serialização |
| **Total** | **41** | **Suíte Python completa** |

Os testes da carga usam *fakes* e não substituem a integração com PostgreSQL.
Os comandos `npm run typecheck` e `npm run build` são validações separadas do
frontend e não entram na contagem de 41 testes Python.

## Entregáveis

| Entregável | Arquivo |
|---|---|
| Enunciado recebido | [Enunciado.md](Enunciado.md) |
| Relatório da Q1 | [docs/01_eda_orders.md](docs/01_eda_orders.md) |
| Schema inferido | [schema.sql](schema.sql) |
| Relatório da Q2 | [docs/02_schema.md](docs/02_schema.md) |
| Carregador e relatório da Q3 | [scripts/load.py](scripts/load.py) · [docs/03_carregamento.md](docs/03_carregamento.md) |
| SQL e relatório da Q4 | [sql/questao_4.sql](sql/questao_4.sql) · [docs/04_analise_clientes.md](docs/04_analise_clientes.md) |
| SQL e relatório da Q5 | [sql/questao_5.sql](sql/questao_5.sql) · [docs/05_dimensao_calendario.md](docs/05_dimensao_calendario.md) |
| Código, relatório e previsões da Q6 | [scripts/questao_6_1.py](scripts/questao_6_1.py) · [docs/06_previsao_demanda.md](docs/06_previsao_demanda.md) · [outputs/questao_6_previsoes.csv](outputs/questao_6_previsoes.csv) |
| Código e ranking da Q7 | [scripts/questao_7_1.py](scripts/questao_7_1.py) · [outputs/questao_7_top_5.csv](outputs/questao_7_top_5.csv) |
| Dashboard interativo local | [dashboard/](dashboard/) · [dashboard/README.md](dashboard/README.md) |
| Contrato agregado do dashboard | [dashboard/public/data/dashboard.json](dashboard/public/data/dashboard.json) |
| Roteiro de apresentação | [docs/08_dashboard_e_apresentacao.md](docs/08_dashboard_e_apresentacao.md) |
| Resumo executivo | [deliverables/LH_Nautical_Resumo_Executivo.pdf](deliverables/LH_Nautical_Resumo_Executivo.pdf) |

## Decisões e trade-offs

| Decisão | Benefício | Limite assumido |
|---|---|---|
| Observar Q1 sem limpeza | Respeita o enunciado e preserva evidência | Não corrige anomalias nem certifica semântica |
| Inferência conservadora por varredura completa | Evita amostra enganosa e mantém tipos úteis | O snapshot não define contrato futuro |
| Não inventar PKs, FKs ou nulabilidade | Evita regras falsas | Integridade fica validada por código, não imposta pelo DDL |
| `COPY FROM STDIN` em transação única | Boa eficiência e rollback integral para 37 MB | Locks e WAL podem pesar em volumes muito maiores |
| Agregar pedidos antes de itens | Evita repetir `orders.total` por item | Exige etapas separadas por granularidade |
| Manter todos os status | Cumpre a regra literal e torna a lacuna visível | Pode incluir valores não reconhecidos pelo negócio |
| Calendário completo à esquerda | Inclui dias POS zerados no denominador | Mede a rede, não loja-dia |
| Média móvel de três meses | Baseline simples, barato e auditável | Ignora sazonalidade, promoções, ruptura e lead time |
| Cosseno sobre interação binária | Recomendação reproduzível e sem peso arbitrário | Afinidade não prova causalidade ou complementaridade |
| JSON agregado entre dados e interface | Navegador não acessa os CSVs brutos | Uma atualização exige regenerar o contrato |
| Clientes rotulados por posição | Preserva utilidade visual sem expor PII | O dashboard não identifica quem deve receber a ação |

## Qualidade e privacidade

O gerador do dashboard lê somente as colunas necessárias. De `customers.csv`,
ele carrega apenas a chave técnica para agregação e publica o top 10 como
`Cliente elite 01` a `Cliente elite 10`. O
[dashboard.json](dashboard/public/data/dashboard.json), os CSVs exportados pelo
dashboard e o PDF utilizam métricas agregadas e aliases, sem nomes, e-mails,
telefones, documentos ou endereços.

Os checks publicados no JSON cobrem:

- inventário e contagem das fontes;
- IDs nulos ou duplicados nas fontes analíticas;
- referências órfãs na cadeia cliente-pedido-item-variante-produto-categoria;
- completude de data, status, canal e `total` em `orders`;
- coerência de `subtotal - discount_amount = total`;
- ausência de campos pessoais na saída do dashboard.

Esses checks demonstram consistência observada, não qualidade semântica
completa. Eles não definem quais status representam venda, não reconciliam
receita contábil e não tornam futuras extrações automaticamente confiáveis.

## Segurança e dados sensíveis

Os CSVs brutos **não são artefatos públicos**. Entre outros campos, eles contêm
nomes, CPF/CNPJ, inscrições, e-mails, telefones e endereços de clientes e
funcionários, além de identificadores fiscais e operacionais.

Antes de publicar, enviar a terceiros ou criar um repositório remoto:

1. remova os 24 CSVs brutos do pacote público e impeça seu versionamento;
2. revise também `outputs/`, pois matrizes e arquivos técnicos podem conter
   chaves pseudônimas de clientes, pedidos ou produtos;
3. publique somente artefatos explicitamente agregados, como o JSON do
   dashboard e o PDF, após revisão;
4. nunca grave DSNs, senhas ou arquivos `.env` no repositório;
5. evite passar senhas por `--dsn`, linha de comando, logs ou capturas de tela;
6. aplique controle de acesso, retenção e descarte adequados às fontes locais.

O fato de o dashboard não conter PII **não torna o repositório inteiro seguro
para publicação**, porque as fontes permanecem na raiz.

## Limitações e próximos passos

- formalizar o contrato de status, moeda, valor reconhecido e data oficial de
  corte antes de publicar KPIs financeiros;
- validar `schema.sql`, `COPY`, locks e rollback em PostgreSQL real;
- transformar o schema inferido em contrato versionado e monitorar *schema
  drift* entre extrações;
- reconciliar pedidos com pagamentos, notas fiscais e devoluções;
- redefinir o grupo elite com recência, frequência mínima, janela temporal e
  resultado incremental;
- avaliar POS por loja, margem, custo de abertura, feriados e sazonalidade;
- ampliar o backtest da previsão e adicionar disponibilidade, ruptura,
  promoção e prazo de fornecedor;
- testar recomendações com grupo de controle antes de qualquer automação;
- confirmar se os registros até 2026-12-31 pertencem ao corte oficial;
- definir uma estratégia de publicação somente depois de separar fontes
  sensíveis dos artefatos compartilháveis.

## Perguntas de defesa

1. **Posso chamar 1,41 bilhão de receita?**  
   Não. É a soma de `orders.total` em todos os status: valor bruto registrado,
   sem reconciliação contábil, de pagamentos ou devoluções.

2. **Por que cancelados e rascunhos foram mantidos?**  
   Porque o desafio não definiu status elegíveis. Excluí-los silenciosamente
   mudaria materialmente Q4, Q5, Q6 e Q7.

3. **Como o ranking de clientes evita duplicar valores?**  
   Métricas monetárias e frequência são calculadas no grão de pedido;
   diversidade é calculada separadamente no grão de item/categoria.

4. **O corte de 13 categorias identifica uma elite?**  
   Pouco: 98,55% dos clientes passam. O resultado cumpre a regra, mas evidencia
   que ela precisa ser redesenhada para segmentação real.

5. **Por que dias sem venda entram como zero?**  
   A operação foi assumida aberta em todo o intervalo. Sem calendário completo,
   o `AVG` ignoraria esses dias e inflaria a média POS.

6. **Quinta-feira deveria fechar?**  
   Não é possível concluir isso. A diferença para domingo é pequena e faltam
   margem, custos, análise por loja, feriados e efeito de migração de demanda.

7. **A previsão usa informação do futuro?**  
   Não no protocolo adotado. Cada mês é previsto com os três meses encerrados
   anteriores; o realizado só entra no histórico depois de sua previsão.

8. **Por que dois produtos entram na previsão?**  
   O nome exato `Bússola de Bordo 702` aparece em dois cadastros. Escolher um ID
   arbitrariamente seria uma regra não fornecida.

9. **A recomendação indica produtos complementares?**  
   Não necessariamente. Ela indica sobreposição de compradores por similaridade
   do cosseno e precisa de teste controlado para demonstrar efeito comercial.

10. **Por que o schema não tem PKs e FKs?**  
    Unicidade e relações observadas em um snapshot não bastam para declarar um
    contrato permanente. O passo correto é aprovar essas regras e então
    adicioná-las.

11. **A carga PostgreSQL foi comprovada de ponta a ponta?**  
    Ainda não. A lógica foi testada com conexões simuladas; falta aplicar o DDL,
    carregar e provocar rollback controlado em uma instância real.

12. **O navegador recebe dados pessoais?**  
    Não. Ele consome o JSON agregado e rankings anonimizados. Os CSVs brutos
    continuam sensíveis e devem permanecer fora de qualquer publicação.

13. **Qual é o próximo gate antes de uma decisão executiva?**  
    Aprovar status, moeda, reconhecimento e corte; depois reconciliar as fontes
    financeiras e testar as ações comerciais de forma incremental.
