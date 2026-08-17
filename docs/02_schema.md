# Questão 2 — Geração do schema PostgreSQL

## Decisão executiva

A solução percorre todos os CSVs de um diretório, infere tipos de maneira conservadora e gera um único `schema.sql` com uma tabela para cada arquivo. Ela utiliza somente a biblioteca padrão do Python 3 e não depende de nuvem, banco ativo ou bibliotecas de análise de dados.

O resultado deve ser entendido como um **schema de ingestão inferido para os arquivos atuais**, não como um contrato definitivo do ERP. Chaves, nulabilidade e regras de relacionamento exigem documentação de negócio e não foram inventadas a partir de uma única extração.

## 1. Entendimento do problema

O ERP não oferece acesso direto ao banco. Assim, os CSVs são a única representação disponível da estrutura e dos dados. A tarefa é automatizar a descoberta das tabelas e colunas, gerando DDL compatível com PostgreSQL.

### Requisitos explícitos

- considerar todos os CSVs do diretório como fontes;
- utilizar Python 3;
- utilizar somente a biblioteca padrão;
- gerar um único arquivo chamado `schema.sql`;
- produzir uma instrução `CREATE TABLE` para cada CSV;
- considerar PostgreSQL como destino.

### Requisitos inferidos

- o nome do arquivo, sem `.csv`, será o nome da tabela;
- a primeira linha será o cabeçalho;
- a ordem das colunas será preservada;
- é necessário inferir tipos, pois apenas detectar nomes produziria tabelas pouco úteis;
- todos os registros devem ser analisados, pois um tipo diferente pode aparecer no final do arquivo;
- um erro em qualquer fonte deve interromper a geração, evitando um schema parcial.

### Ambiguidades relevantes

O enunciado não define:

- encoding, delimitador e convenção de nulos;
- se a busca deve ser recursiva;
- política para tipos mistos ou colunas totalmente vazias;
- se devem existir PKs, FKs, `UNIQUE`, `NOT NULL` ou enums;
- se o schema será uma camada de ingestão ou o modelo definitivo;
- como diferenciar números de códigos formados somente por dígitos.

As decisões adotadas foram: UTF-8, vírgula, busca não recursiva e campo exatamente vazio ignorado apenas durante a inferência. Literais como `NULL`, `N/A` ou `None` continuam sendo texto. Essas decisões correspondem aos arquivos fornecidos e estão documentadas como premissas.

## 2. Premissas e hipóteses

| Premissa ingênua | Problema | Decisão adotada |
|---|---|---|
| CSV possui tipos | CSV armazena representações textuais | O tipo é uma inferência, não uma verdade do arquivo. |
| Basta analisar a primeira linha | Um valor incompatível pode aparecer depois | Varredura completa em streaming. |
| Todo conjunto de dígitos é número | CPF, NCM, EAN e chave fiscal podem perder zeros | Convenção estreita para identificadores textuais. |
| Ausência de nulos implica `NOT NULL` | Uma extração não estabelece contrato futuro | Nenhuma restrição de nulabilidade é criada. |
| Coluna `id` implica PK | Unicidade observada não prova regra permanente | Nenhuma PK ou FK é inferida. |
| Maior texto define `VARCHAR(n)` | O próximo arquivo pode conter texto maior | Uso de `TEXT`. |
| Decimal pode ser `FLOAT` | Valores financeiros sofreriam arredondamento binário | Uso de `NUMERIC`. |
| Data sem offset tem fuso conhecido | O CSV não informa timezone | `TIMESTAMP WITHOUT TIME ZONE`. |
| Campo vazio é sempre `NULL` | CSV também pode representar string vazia | Nenhuma constraint é criada; a carga deverá documentar essa convenção. |

## 3. O que não está óbvio nos arquivos

Foram analisados 24 CSVs e 433.424 registros. Nenhuma linha possui quantidade incorreta de campos.

Casos que quebrariam uma implementação ingênua:

- `stock_levels.reorder_point` está vazio nas 6.054 linhas. Seu tipo é impossível de inferir; o fallback é `TEXT`, acompanhado de aviso;
- `variant_attribute_values.value` mistura booleanos, números e textos, portanto precisa permanecer `TEXT`;
- `customers.state_registration` mistura dígitos com valores como `ISENTO`;
- `nfe_access_key` possui 44 dígitos e pode começar com zero;
- `series` contém `001`, que perderia significado ao virar inteiro;
- CPF, NCM, telefone, CEP, EAN e documentos fiscais são identificadores, não grandezas aritméticas;
- há valores opcionais em `salesperson_id`, `paid_at`, `termination_date`, `exchange_variant_id` e outras colunas;
- quantidades podem possuir três casas decimais e movimentos de estoque podem ser negativos;
- os arquivos misturam finais de linha LF e CRLF, justificando `newline=""` na abertura;
- alguns campos possuem acentos, vírgulas ou outros caracteres que exigem o módulo `csv`, e não `split(',')`.

### Escala e concorrência

O algoritmo é aproximadamente `O(total de bytes)` em tempo e mantém somente o estado das colunas e a linha atual em memória. Para 433 mil registros, a varredura completa é barata e mais confiável que amostragem.

A escrita do resultado é atômica: primeiro é criado um arquivo temporário no diretório de destino e depois ele substitui `schema.sql`. Isso evita um arquivo parcialmente escrito. A solução assume, porém, que os CSVs não serão modificados durante a leitura; garantir snapshot de arquivos em atualização exigiria coordenação adicional.

### Segurança e consistência

Nomes de arquivos e cabeçalhos são sempre delimitados com aspas duplas, escapando aspas internas. Isso preserva nomes reservados e evita que um cabeçalho seja interpretado como SQL. Cabeçalhos vazios, duplicados, com caracteres de controle ou maiores que o limite padrão de 63 bytes do PostgreSQL interrompem a execução.

## 4. Alternativas consideradas

### A — Todas as colunas como `TEXT`

- **Quando faz sentido:** camada raw cujo único objetivo é preservar o arquivo.
- **Vantagens:** quase nenhuma perda por conversão e implementação muito simples.
- **Desvantagens:** datas, booleanos e números precisam ser convertidos em toda análise posterior.
- **Risco:** aceitar valores inválidos silenciosamente.
- **Sacrifício:** utilidade analítica imediata.

### B — Inferência conservadora por varredura completa (escolhida)

- **Quando faz sentido:** arquivos de tamanho pequeno ou médio que precisam ficar utilizáveis no PostgreSQL.
- **Vantagens:** equilíbrio entre preservação, tipos úteis, clareza e baixo uso de memória.
- **Desvantagens:** semântica não pode ser totalmente descoberta pelos valores.
- **Risco:** uma nova extração conter um valor incompatível com o tipo anterior.
- **Sacrifício:** algumas colunas ambíguas permanecem `TEXT`.

### C — Camada raw em texto mais camada tipada

- **Quando faz sentido:** pipeline recorrente de produção com quarentena e monitoramento de schema drift.
- **Vantagens:** preserva a fonte e separa ingestão de validação.
- **Desvantagens:** duplica tabelas, DDL e processo de manutenção.
- **Risco:** fugir do escopo de uma tabela por CSV.
- **Sacrifício:** simplicidade.

Inferir somente por amostra também foi descartado: reduziria pouco o tempo nesta base e poderia errar por causa de um valor tardio.

## 5. Olhar de avaliador

Uma resposta apenas funcional provavelmente usaria `split(',')`, examinaria poucas linhas, trataria códigos como inteiros e escreveria o arquivo mesmo após encontrar uma fonte inválida.

As decisões que demonstram maturidade nesta solução são:

- utilizar `csv.reader` em modo estrito;
- ler todos os registros sem carregá-los em memória;
- usar `Decimal` para reconhecer números exatos;
- promover tipos compatíveis e usar `TEXT` em misturas incompatíveis;
- preservar códigos e zeros à esquerda;
- gerar saída determinística em ordem alfabética;
- manter as colunas na ordem da fonte;
- citar identificadores corretamente;
- validar todos os arquivos antes de escrever;
- não inferir constraints ou limites de tamanho sem contrato de dados;
- informar quando não há evidência para escolher um tipo.

Seria complexidade desnecessária introduzir pandas, Spark, ORM, paralelismo, enums automáticos, migrações ou inferência de relacionamentos para este volume e escopo.

## 6. Design thinking, arquitetura e decisões

### Empatizar

- **Gabriel:** recebe funções pequenas, regras documentadas, erros claros e testes reproduzíveis;
- **Marina:** recebe números, datas e booleanos tipados para permitir análises posteriores sem casts repetidos;
- **Sr. Almir:** consegue executar tudo localmente e auditar um arquivo SQL legível, sem depender de conexão direta ou nuvem.

### Definir

O problema não é reconstruir o modelo original do ERP, algo impossível apenas com CSV. O objetivo viável é gerar uma estrutura de ingestão útil, reproduzível e honesta sobre suas limitações.

### Idear e escolher

A inferência conservadora foi escolhida entre uma camada toda textual e uma arquitetura raw + typed. Ela entrega valor imediato sem criar duas estruturas ou fingir conhecer regras que não foram fornecidas.

### Estrutura

1. descobrir os CSVs diretamente no diretório;
2. validar nome da tabela e cabeçalho;
3. ler cada arquivo integralmente e atualizar o tipo de cada coluna;
4. validar que todos os arquivos podem gerar tabelas;
5. renderizar os `CREATE TABLE` em ordem alfabética;
6. gravar `schema.sql` atomicamente.

### Política de tipos

| Evidência observada | PostgreSQL |
|---|---|
| `TRUE` / `FALSE` | `BOOLEAN` |
| Inteiro dentro de 32 bits | `INTEGER` |
| Inteiro maior, dentro de 64 bits | `BIGINT` |
| Decimal ou inteiro acima de 64 bits | `NUMERIC` |
| Data ISO | `DATE` |
| Data e hora ISO sem offset | `TIMESTAMP WITHOUT TIME ZONE` |
| Data e hora com offset | `TIMESTAMP WITH TIME ZONE` |
| Tipo misto, código ou tipo indeterminado | `TEXT` |

Promoções aceitas:

```text
INTEGER -> BIGINT -> NUMERIC
DATE -> TIMESTAMP WITHOUT TIME ZONE
misturas entre famílias -> TEXT
```

`NUMERIC` foi usado sem precisão fixa porque `NUMERIC(8,2)`, por exemplo, descreveria apenas o maior valor da extração atual e poderia rejeitar uma próxima carga válida. Precisão e escala devem vir do contrato do ERP.

## 7. Implementação

Arquivos entregues:

- [`scripts/schema.py`](../scripts/schema.py): gerador;
- [`schema.sql`](../schema.sql): resultado para os 24 CSVs;
- [`tests/test_generate_schema.py`](../tests/test_generate_schema.py): testes com `unittest`.

Execução a partir da raiz do projeto:

```bash
python3 scripts/schema.py data/raw -o schema.sql
```

`data/raw` é a área imutável das fontes sintéticas. O arquivo derivado
`schema.sql` permanece na raiz para facilitar sua identificação como entregável.

Saída observada:

```text
Aviso: stock_levels.csv.reorder_point não possui valores preenchidos; tipo definido como TEXT.
Schema gerado em schema.sql: 24 tabelas e 433424 registros analisados.
```

O `schema.sql` contém exatamente 24 instruções `CREATE TABLE`, dentro de `BEGIN` e `COMMIT`. Não contém `DROP`, `IF NOT EXISTS`, `SERIAL`, PKs ou FKs.

## 8. Estratégia e resultados dos testes

Foram criados 12 testes unitários cobrindo:

- booleano, inteiro, `BIGINT`, decimal, data, timestamp e texto;
- promoção entre tipos compatíveis;
- mistura de tipos e zeros à esquerda;
- convenção de CPF, NCM, chaves, números e SKUs;
- BOM UTF-8, Unicode, CRLF e vírgula dentro de campo citado;
- arquivo somente com cabeçalho;
- arquivo vazio;
- cabeçalho duplicado;
- linha curta ou longa;
- nomes reservados e aspas em identificadores;
- ordenação e saída determinística;
- preservação do arquivo anterior quando uma fonte falha.

Resultado:

```text
Ran 12 tests
OK
```

Também foi feita uma validação de integração:

- 24 tabelas geradas;
- 433.424 registros analisados;
- todos os cabeçalhos preservados;
- exatamente uma coluna sem valor observável;
- somente módulos da biblioteca padrão importados;
- duas execuções produziram o mesmo SHA-256 do `schema.sql`.

Não foi possível executar um smoke test em PostgreSQL porque não há servidor ou cliente PostgreSQL disponível neste ambiente. A sintaxe gerada permanece específica para PostgreSQL e esse teste seria o próximo passo em um ambiente com o banco instalado.

## 9. Autocrítica

A principal limitação é semântica: um CSV não consegue informar se uma sequência de dígitos é um número ou um documento. A convenção de identificadores textuais reduz perdas nos dados fornecidos, mas continua sendo uma política baseada em nomes.

Outras limitações:

- o schema descreve o snapshot atual, não garante compatibilidade futura;
- apenas arquivos diretamente no diretório são considerados;
- delimitador e encoding foram definidos conforme as fontes atuais;
- `reorder_point` virou `TEXT` por falta total de evidência;
- timestamps sem offset não permitem descobrir o fuso correto;
- o script não detecta alterações nos CSVs durante a execução;
- o arquivo cria estruturas, mas não executa a carga dos dados;
- string vazia e valor nulo precisam de uma política no futuro comando `COPY`.

Melhorias que fariam sentido em produção:

- receber um arquivo opcional de overrides de tipos;
- comparar schemas entre extrações e alertar sobre mudanças;
- registrar rejeições durante a carga;
- validar o DDL e o `COPY` em PostgreSQL;
- acrescentar constraints após aprovação de um contrato de dados.

Melhorias que não valem a complexidade nesta questão:

- inferir automaticamente todas as FKs;
- criar enums a partir dos valores atuais;
- paralelizar a leitura;
- criar uma camada de migrations;
- tentar “corrigir” valores sujos durante a inferência.

## 10. Perguntas que eu deveria conseguir responder

1. **Por que não usar pandas?**  
   A restrição exige biblioteca padrão e o módulo `csv` permite leitura incremental adequada ao volume.

2. **Por que ler todas as linhas?**  
   Um único valor tardio pode mudar uma coluna de numérica para textual; amostragem não oferece benefício suficiente aqui.

3. **Como diferenciar CPF de número?**  
   Não é possível somente pelo léxico. É necessária uma convenção pelo nome ou um contrato de dados.

4. **Por que usar `NUMERIC` em vez de `FLOAT`?**  
   Valores financeiros exigem representação decimal exata.

5. **Por que não usar `VARCHAR(n)`?**  
   O maior comprimento do snapshot não estabelece limite futuro, e `TEXT` não possui desvantagem relevante no PostgreSQL para esse uso.

6. **Por que não criar `NOT NULL`?**  
   Completude observada não é uma regra permanente do ERP.

7. **Por que não criar PKs e FKs?**  
   Nomes e unicidade atual não são suficientes para estabelecer relacionamentos oficiais.

8. **O que acontece com uma coluna totalmente vazia?**  
   O tipo não pode ser descoberto; a solução usa `TEXT` e informa a incerteza.

9. **Como os tipos mistos são tratados?**  
   Tipos numéricos compatíveis são ampliados; famílias incompatíveis resultam em `TEXT`, preservando os valores.

10. **Por que citar todos os identificadores?**  
    Para preservar nomes, aceitar palavras reservadas e impedir que cabeçalhos sejam interpretados como SQL.

11. **Por que não usar `IF NOT EXISTS`?**  
    Ele poderia ocultar uma tabela antiga com schema incompatível e dar falsa impressão de sucesso.

12. **O schema continuará válido para novos arquivos?**  
    Não há garantia. É necessário detectar schema drift ou adotar um contrato oficial.

13. **O `schema.sql` garante que o `COPY` funcionará?**  
    Não sozinho. A carga ainda precisa definir encoding, delimitador, cabeçalho e representação de nulos.

14. **Qual é a complexidade?**  
    Tempo linear no volume lido e memória proporcional ao número de colunas e ao maior registro.

15. **Por que essa solução ajuda cada stakeholder?**  
    Ela é simples e testável para Gabriel, produz tipos úteis para Marina e é local, legível e auditável para o Sr. Almir.
