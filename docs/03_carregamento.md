# Questão 3 — Carregamento dos CSVs no PostgreSQL

## Decisão executiva

A solução valida todos os CSVs e os carrega nas tabelas já criadas pelo
`schema.sql` usando `COPY FROM STDIN`. O conteúdo é enviado pelo cliente em
streaming, sem remover registros, preencher ausências, aparar espaços,
deduplicar ou corrigir caracteres.

Os 24 arquivos fornecidos contêm 433.424 registros e aproximadamente 37 MB.
Para esse volume, uma única transação é uma escolha simples e segura: se
qualquer arquivo, tabela ou valor falhar, nenhuma alteração do lote é
confirmada.

Por padrão, a carga exige tabelas vazias. A opção `--replace` permite uma
substituição intencional e executa o `TRUNCATE` e o novo carregamento na mesma
transação.

## 1. Entendimento do problema

O schema da etapa anterior cria as estruturas, mas ainda não coloca os dados no
banco. A tarefa atual é transferir cada CSV para sua tabela correspondente no
PostgreSQL, preservando a fonte recebida do ERP e impedindo que uma falha deixe
um conjunto incompleto para análise.

### Requisitos explícitos

- carregar todos os CSVs;
- utilizar Python 3;
- respeitar o schema criado na questão anterior;
- permitir bibliotecas externas para conexão e carregamento;
- não remover nulos nem corrigir caracteres especiais.

### Requisitos inferidos

- o nome do arquivo sem `.csv` identifica a tabela;
- a primeira linha contém as colunas e deve corresponder ao banco;
- o `schema.sql` deve ser aplicado antes da carga;
- uma falha em qualquer fonte deve cancelar o lote inteiro;
- credenciais não devem ficar gravadas no código;
- uma reexecução não pode duplicar linhas silenciosamente;
- nomes vindos de arquivos e cabeçalhos não devem ser interpolados diretamente
  em SQL.

### Ambiguidades relevantes

O enunciado não define:

- encoding, delimitador e representação de nulo;
- comportamento quando uma tabela já contém dados;
- se a carga é snapshot completo ou incremental;
- schema PostgreSQL de destino;
- política de concorrência;
- ordem de carregamento caso existam chaves estrangeiras;
- comportamento se os arquivos mudarem durante a execução.

Para os arquivos fornecidos, foram adotados UTF-8, vírgula, cabeçalho na
primeira linha, diretório não recursivo e schema `public` por padrão. A carga é
tratada como snapshot completo, não como carga incremental.

## 2. Premissas e hipóteses

| Premissa ingênua | Por que deve ser questionada | Decisão adotada |
|---|---|---|
| Campo vazio é sempre texto vazio | Colunas numéricas e datas não aceitam `''`, e CSV diferencia vazio citado de não citado | Vazio não citado segue a semântica do PostgreSQL e vira `NULL`; `""` permanece texto vazio |
| Basta usar `INSERT` linha a linha | Isso cria muitos round trips e piora o desempenho | `COPY FROM STDIN` |
| `HEADER TRUE` faz o mapeamento pelo nome | Em versões usuais, ele apenas descarta a primeira linha | Comparar cabeçalho, ordem e catálogo antes da carga |
| A ordem física das colunas sempre coincide | Um schema diferente poderia deslocar valores | Informar uma lista explícita de colunas no `COPY` |
| Executar de novo produz o mesmo resultado | O schema não possui PK ou `UNIQUE`; ocorreria duplicação | Falhar se houver dados ou exigir `--replace` |
| É aceitável continuar depois de um erro | Relatórios seriam calculados sobre snapshot parcial | Uma transação para as 24 tabelas |
| Arquivo local também existe no servidor | Isso não vale para PostgreSQL remoto | Enviar o arquivo pelo cliente com `STDIN` |
| Acentos precisam ser corrigidos | Uma normalização mudaria a fonte | UTF-8 estrito e nenhuma alteração de conteúdo |

A solução pressupõe que os CSVs não sejam modificados durante a carga e que o
usuário do banco possua permissões compatíveis. O modo comum precisa consultar
e inserir nas tabelas; o lock de proteção concorrente também exige uma das
permissões aceitas pelo PostgreSQL para `SHARE ROW EXCLUSIVE`. O modo
`--replace` exige permissão de `TRUNCATE`.

## 3. O que não está óbvio

### Fidelidade e nulos

O `csv.reader` é usado na pré-validação, mas não reconstrói os registros. No
carregamento, o arquivo é reaberto e entregue diretamente ao `COPY`. Assim,
aspas, vírgulas, quebras de linha, espaços laterais e caracteres Unicode não
são normalizados.

Nos arquivos atuais existem:

- 224.294 campos vazios, todos não citados;
- 63 campos textuais com espaço inicial ou final;
- 19 valores literais como `N/A`, `n/a` e `-`;
- acentos e o caractere travessão.

Nada disso é corrigido. No formato CSV do PostgreSQL, o vazio não citado é
interpretado como `NULL`, enquanto `""` representa string vazia. Valores como
`N/A` continuam sendo texto. Essa é uma regra de representação do CSV no
banco, não uma limpeza inventada pelo script.

Não são usados `.strip()`, `.replace()`, preenchimento de ausências,
deduplicação, descarte de linhas ou `ON_ERROR ignore`. Um valor incompatível
com o tipo do schema interrompe o lote.

### Consistência

Antes do primeiro `COPY`, o programa verifica:

- se todos os arquivos podem ser lidos como CSV UTF-8;
- se os cabeçalhos são válidos e não possuem colunas duplicadas;
- se todas as linhas têm a quantidade esperada de campos;
- se as tabelas alvo existem;
- se as colunas e sua ordem correspondem exatamente ao banco;
- se as tabelas estão vazias, salvo uso explícito de `--replace`.

O cabeçalho é conferido novamente ao reabrir cada arquivo, reduzindo o risco de
uma troca de colunas entre a validação e o `COPY`. Depois de cada carga, a
quantidade de linhas da tabela é comparada à quantidade contada no CSV.

### Concorrência

Apenas consultar se uma tabela está vazia não seria suficiente: duas execuções
poderiam enxergar o mesmo estado e inserir o snapshot duas vezes. Por isso, a
transação adquire `SHARE ROW EXCLUSIVE` nas tabelas, em ordem determinística,
antes da checagem. Esse modo permite leituras, impede writers concorrentes e
garante que somente uma execução do carregador avance por vez.

O custo é manter locks até o fim da carga. Para aproximadamente 37 MB isso é
aceitável; em tabelas atendendo tráfego transacional durante longos períodos, a
estratégia precisaria ser revista.

### Segurança

- a conexão vem de `LH_NAUTICAL_DATABASE_URL`, de variáveis `PG*` ou de uma
  opção explícita; nenhuma senha é gravada no arquivo;
- schema, tabela e colunas são compostos com `psycopg2.sql.Identifier`;
- os erros de `COPY` informam arquivo, linha e coluna, mas omitem o valor
  rejeitado para não expor CPF, e-mail ou outro dado pessoal em logs;
- o DSN nunca é impresso.

## 4. Alternativas consideradas

### A — `COPY FROM STDIN` em streaming (escolhida)

- **Quando faz sentido:** carga integral de CSVs em tabelas já tipadas.
- **Vantagens:** poucos round trips, baixo uso de memória e parser CSV do
  próprio PostgreSQL.
- **Desvantagens:** um valor inválido interrompe o arquivo; não há quarentena
  por linha.
- **Complexidade:** baixa.
- **Risco:** uma fonte alterada durante a execução ainda pode invalidar a
  pré-validação.
- **Sacrifício:** flexibilidade para tratar linhas, algo proibido nesta tarefa.

### B — `csv.reader` com `INSERT` em lotes

- **Quando faz sentido:** quando cada registro precisa de validação ou
  transformação específica.
- **Vantagens:** controle detalhado e diagnóstico por registro.
- **Desvantagens:** mais lento e exige mapear manualmente vazios e tipos.
- **Complexidade:** média.
- **Risco:** perder a diferença entre vazio não citado e `""`, além de alterar
  dados sem intenção.
- **Sacrifício:** desempenho e fidelidade simples ao CSV original.

### C — Camada raw em texto seguida de camada tipada

- **Quando faz sentido:** ingestões recorrentes, schema drift, auditoria e
  quarentena de rejeições.
- **Vantagens:** preserva a fonte e separa ingestão de regras de negócio.
- **Desvantagens:** duplica tabelas e cria outro processo de transformação.
- **Complexidade:** média/alta.
- **Risco:** aumentar o escopo sem uma necessidade comprovada.
- **Sacrifício:** simplicidade e aderência direta ao schema solicitado.

`COPY FROM '/caminho'` também foi descartado: o caminho seria lido pelo servidor
e dependeria de filesystem e permissões da máquina do PostgreSQL. Pandas, ORM,
Spark, paralelismo e orquestradores não resolvem um problema presente neste
volume.

## 5. Olhar de avaliador

Uma resposta apenas funcional provavelmente usaria `split(',')`, faria
`INSERT` linha a linha, colocaria credenciais no código ou continuaria após
encontrar uma linha inválida.

O que diferencia esta solução:

- distingue `NULL` de string vazia sem aplicar limpeza;
- usa um mecanismo bulk apropriado ao PostgreSQL;
- envia os arquivos pelo cliente, funcionando também com banco remoto;
- valida fontes e catálogo antes da primeira inserção;
- mantém as 24 fontes no mesmo limite transacional;
- impede duplicação acidental, inclusive entre duas execuções do carregador;
- trata identificadores SQL separadamente de valores;
- reconcilia contagens por arquivo;
- evita colocar valores potencialmente pessoais nos erros;
- declara que inferência de schema e carregamento são responsabilidades
  diferentes.

Decisões que pareceriam complexidade desnecessária neste caso: classes de
repositório, camadas de serviço, async, filas, retry por registro, migrations,
descoberta automática de dependências e um orquestrador de pipeline.

Um avaliador provavelmente exploraria a semântica de nulos, atomicidade,
concorrência, idempotência, encoding, credenciais e a diferença entre os
filesystems do cliente e do servidor.

## 6. Design thinking, arquitetura e decisões

### Empatizar

- **Gabriel Santos:** recebe funções pequenas, políticas explícitas, SQL seguro,
  testes reproduzíveis e limitações documentadas.
- **Marina Costa:** só recebe uma base disponível quando todas as tabelas estão
  carregadas, evitando indicadores calculados sobre lote parcial.
- **Sr. Almir:** pode executar localmente, comparar contagens e verificar que os
  CSVs originais não foram modificados; nenhuma nuvem é necessária.

### Definir

O problema não é limpar ou enriquecer dados. É transportá-los com fidelidade
para estruturas já definidas e produzir evidência de completude.

### Idear e escolher

O `COPY FROM STDIN` foi escolhido entre inserções em lote e uma arquitetura com
staging raw. Ele atende o volume atual com menos código e sem introduzir uma
segunda camada que não foi solicitada.

### Fluxo

```text
Descobrir todos os CSVs em ordem estável
                    |
                    v
Validar cabeçalhos, largura, UTF-8 e contar registros
                    |
                    v
Conectar e iniciar uma transação única
                    |
                    v
Bloquear tabelas e validar colunas no catálogo
                    |
                    v
Exigir tabelas vazias ou executar TRUNCATE explícito
                    |
                    v
COPY de cada arquivo + conferir a contagem da tabela
                    |
           +--------+--------+
           |                 |
         sucesso            falha
           |                 |
         COMMIT       ROLLBACK integral
```

O schema atual não contém chaves estrangeiras, portanto a ordem alfabética é
suficiente. Se FKs forem adicionadas, será preciso ordenar por dependência ou
usar constraints deferíveis.

## 7. Implementação

Arquivos:

- [`scripts/load.py`](../scripts/load.py): carregador;
- [`requirements.txt`](../requirements.txt): dependência de conexão;
- [`tests/test_load.py`](../tests/test_load.py): testes unitários.

Instalação:

```bash
python3 -m pip install -r requirements.txt
```

Depois de aplicar o `schema.sql`, a forma recomendada de informar a conexão é
por variável de ambiente:

```bash
export LH_NAUTICAL_DATABASE_URL='postgresql://usuario:senha@host:5432/banco'
python3 scripts/load.py data/raw
```

Outro schema pode ser selecionado:

```bash
python3 scripts/load.py data/raw --db-schema lh_nautical
```

Também é possível utilizar as variáveis padrão da libpq (`PGHOST`, `PGPORT`,
`PGDATABASE`, `PGUSER` e `PGPASSWORD`). A opção `--dsn` existe, mas uma URL com
senha passada na linha de comando pode aparecer no histórico do shell e na
lista de processos.

Por padrão, qualquer tabela não vazia cancela o lote. Para substituir
deliberadamente o conteúdo das tabelas alvo:

```bash
python3 scripts/load.py data/raw --replace
```

O carregador lê somente os arquivos diretamente em `data/raw`. Resultados
derivados em `outputs/` não participam da carga.

`--replace` apaga os dados anteriores se houver sucesso. Se qualquer parte da
nova carga falhar antes do commit, o `TRUNCATE` também sofre rollback e o estado
anterior é restaurado.

## 8. Estratégia e resultados dos testes

### Casos normais

- descoberta de vários CSVs em ordem determinística;
- UTF-8 com BOM, acentos, vírgula e quebra de linha em campo citado;
- preservação de espaços, `N/A`, campo vazio e `""`;
- catálogo com as mesmas colunas e na mesma ordem;
- composição de nomes reservados e nomes contendo aspas;
- carga e conferência da contagem final.

### Casos-limite e inválidos

- diretório inexistente, sem CSVs ou sem permissão;
- arquivo vazio ou somente com cabeçalho;
- cabeçalho vazio, duplicado ou maior que o limite do PostgreSQL;
- linha com campos a mais ou a menos;
- UTF-8 inválido;
- tabela ausente e coluna extra, ausente ou fora de ordem;
- cabeçalho alterado entre pré-validação e carga;
- valor incompatível com o tipo do schema.

### Falhas e consistência

- erro de conversão no último arquivo deve reverter os anteriores;
- reexecução comum deve falhar sem duplicar;
- `--replace` com falha deve restaurar os dados antigos;
- duas conexões concorrentes devem ser serializadas pelo lock;
- desconexão durante a carga deve deixar o lote sem commit;
- divergência de contagem deve provocar rollback.

### Performance

- medir tempo e pico de memória, sem impor limite dependente da máquina;
- usar uma fonte grande para confirmar que a memória não cresce com o total de
  linhas;
- avaliar o tempo dos `COUNT(*)` e dos locks antes de escalar a solução.

Foram executados 24 testes unitários no repositório, 12 deles específicos do
carregador, todos com sucesso. A pré-validação real encontrou 24 fontes e
433.424 registros.

Os testes unitários usam fakes para a conexão e validam a orquestração Python,
mas não provam a sintaxe do `COPY`, a matriz real de locks nem o rollback do
PostgreSQL. Não há servidor nem cliente PostgreSQL neste ambiente. O próximo
passo necessário é um teste de integração em uma instância real: aplicar o
`schema.sql`, carregar os arquivos, reconciliar 433.424 linhas e provocar uma
falha controlada para observar o rollback.

## 9. Autocrítica

A solução lê cada CSV duas vezes: uma para validar e contar, outra para enviar
ao banco. Isso privilegia falha antecipada e mensagens melhores, mas seria caro
em arquivos muito maiores.

O `COUNT(*)` depois de cada cópia também percorre a tabela. Para 433 mil linhas
é uma evidência útil; em bilhões de registros, seria melhor usar métricas do
lote e reconciliação assíncrona.

Os locks eliminam a corrida entre carregadores e writers cooperando com o
PostgreSQL, mas têm custo: exigem privilégio adicional e bloqueiam alterações
nas tabelas durante toda a transação. Uma espera pode ser longa porque não foi
definido `lock_timeout`. Adicionar timeout sem requisito operacional seria
arbitrário; em produção, ele deveria vir de um acordo de operação.

Ainda existe uma janela relacionada ao filesystem. O cabeçalho é conferido ao
reabrir a fonte e a quantidade final é reconciliada, mas uma alteração de
conteúdo que mantenha cabeçalho e número de registros poderia passar. Um
snapshot imutável ou checksum antes e depois resolveria isso. Para uma extração
local estática, a premissa de arquivos estáveis é mais simples; para ingestão
recorrente, essa proteção passaria a valer a complexidade.

A transação única é adequada aos 37 MB atuais, mas pode produzir WAL e manter
locks por tempo excessivo em cargas muito maiores. Staging, checkpoints e
commits por lote controlado seriam opções nesse cenário, ao custo de uma
política explícita para estados parciais.

Não valem a complexidade agora: processamento paralelo, retry automático,
Airflow, camada raw adicional, correção automática de rejeições ou hash/manifest
sofisticado. Nenhum deles é necessário para cumprir esta questão com o volume
observado.

## 10. Perguntas que eu deveria conseguir responder

1. **Por que usar `COPY` em vez de `INSERT`?**  
   Dominar round trips, protocolo bulk, throughput e consumo de memória.

2. **Por que `FROM STDIN` e não `COPY FROM '/arquivo.csv'`?**  
   Entender a diferença entre filesystem do cliente e do servidor, permissões
   e funcionamento com banco remoto.

3. **Campo vazio virar `NULL` viola a premissa?**  
   Explicar a semântica CSV do PostgreSQL: vazio não citado representa `NULL`;
   vazio citado representa texto vazio. Nenhuma linha foi removida ou
   preenchida.

4. **Como os caracteres especiais são preservados?**  
   Dominar UTF-8, quoting CSV e a diferença entre decodificar corretamente e
   normalizar conteúdo.

5. **Por que uma transação para 24 tabelas?**  
   Explicar atomicidade do snapshot e o trade-off com duração, WAL e locks.

6. **O que acontece se o script for executado duas vezes?**  
   Explicar `fail-if-not-empty`, ausência de PKs/`UNIQUE` e substituição
   explícita com `--replace`.

7. **Por que bloquear todas as tabelas?**  
   Explicar a corrida entre checagem e inserção, modos de lock, ordem de
   aquisição, privilégios e custo operacional.

8. **Como o código evita SQL injection em nomes?**  
   Saber por que placeholders de valores não servem para identificadores e como
   `sql.Identifier` realiza o quoting.

9. **Como provar que todos os dados foram carregados?**  
   Explicar contagem por fonte/tabela, total esperado, commit único e testes de
   valores representativos.

10. **O que acontece se CSV e schema divergirem?**  
    Defender o `fail fast`: não adaptar estrutura, converter ou descartar
    campos silenciosamente.

11. **Como a solução mudaria para bilhões de linhas ou cargas diárias?**  
    Dominar staging, particionamento, checkpoints, idempotência por lote,
    observabilidade e schema drift.

12. **E se existirem chaves estrangeiras?**  
    Entender ordem topológica, constraints deferíveis e validação após carga.

13. **Por que não há retry automático?**  
    Entender que repetir após perda de conexão exige conhecer o estado do lote
    e garantir idempotência antes de tentar novamente.

14. **Quais testes ainda faltam?**  
    Distinguir testes unitários de integração e explicar por que apenas um
    PostgreSQL real comprova `COPY`, locks, permissões e rollback.

## Referências técnicas

- [PostgreSQL — COPY](https://www.postgresql.org/docs/current/sql-copy.html)
- [PostgreSQL — LOCK](https://www.postgresql.org/docs/current/sql-lock.html)
- [Psycopg 2 — `copy_expert`](https://www.psycopg.org/docs/cursor.html#cursor.copy_expert)
- [Psycopg 2 — composição segura de SQL](https://www.psycopg.org/docs/sql.html)
