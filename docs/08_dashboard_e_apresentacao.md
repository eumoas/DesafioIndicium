# Dashboard e apresentação executiva

## O que entregar

A entrega complementar combina dois formatos:

- [`dashboard/`](../dashboard/README.md): exploração interativa por perspectiva;
- [`LH_Nautical_Resumo_Executivo.pdf`](../deliverables/LH_Nautical_Resumo_Executivo.pdf): narrativa fixa de oito páginas, em 16:9, para leitura ou apresentação.

O dashboard é executado localmente. Esta documentação não pressupõe URL pública,
hospedagem ou implantação já realizada.

## Roteiro de defesa — aproximadamente 6 minutos

### 0:00–0:30 · Abra pela Ponte de Comando

Comece pela decisão, não pela ferramenta. O snapshot reúne **48.998 pedidos** e
**1,41 bilhão em valor registrado** entre 2020 e 2026. Antes de interpretar esse
valor, ressalve que a soma inclui todos os status e não representa receita
reconhecida, lucro ou caixa.

### 0:30–2:10 · Marina: onde agir comercialmente

Na visão **Marina**, mostre o ranking anonimizado, as categorias do grupo elite e
a comparação de canais.

Mensagem principal: o corte de pelo menos 13 categorias aprova 1.971 de 2.000
clientes, ou 98,55% da base. Portanto, ele é pouco seletivo e o ticket médio
domina quase todo o ranking. **Hélices** lidera a soma de `quantity` no top 10,
enquanto o e-commerce concentra cerca de 70% do valor registrado. Esses sinais
servem para formular testes de oferta; não demonstram margem, fidelidade ou
causalidade.

### 2:10–3:50 · Sr. Almir: o que é verificável

Na visão **Sr. Almir**, explique primeiro o calendário completo do POS: dias sem
registro entram como zero antes da média. Quinta-feira é o menor dia da rede,
mas fica apenas 461,81 abaixo de domingo, diferença de aproximadamente 0,29%.
Isso não sustenta, sozinho, fechamento de loja.

Em seguida, mostre o teste da previsão. A média móvel de três meses teve MAE de
19,44 unidades e subestimou o primeiro trimestre de 2026 em 58,33 unidades. É um
baseline auditável, não uma ordem automática de compra; estoque disponível,
ruptura, promoção e prazo de reposição ainda não entram no modelo.

### 3:50–5:30 · Gabriel: como o número foi produzido

Na visão **Gabriel**, percorra a linhagem CSVs → agregação →
[`dashboard.json`](../dashboard/public/data/dashboard.json) → interface. Mostre
as 24 fontes inventariadas, os 433.424 registros e os checks publicados. Explique
que o navegador recebe agregados e rótulos de posição, sem nomes, contatos,
documentos ou endereços de clientes.

Feche a parte técnica com os limites: a consistência observada permite
exploração, mas a definição dos status elegíveis, da moeda e da data oficial de
corte ainda é um gate de governança.

### 5:30–6:00 · Conclusão

Proponha três próximos passos, nesta ordem:

1. aprovar o contrato das métricas — status, moeda, reconhecimento e corte;
2. testar o cross-sell com grupo de controle e resultado incremental;
3. comparar o baseline de demanda com alternativas que incluam estoque, ruptura
   e lead time.

## Perguntas que orientam a exploração

| Perspectiva | Pergunta | Onde observar | Cuidado de interpretação |
|---|---|---|---|
| Ponte de Comando | Como o valor registrado evolui no snapshot? | Trajetória mensal | Crescimento no arquivo não prova receita reconhecida. |
| Ponte de Comando | Qual canal concentra mais valor e pedidos? | Composição por canal | Volume não informa margem nem custo de servir. |
| Marina | Quem o critério atual prioriza? | Top 10 por ticket médio | O ranking usa aliases; frequência não filtra nem ordena. |
| Marina | O corte de 13 categorias realmente diferencia clientes? | Cobertura do critério | 98,55% passam, logo o corte é pouco seletivo. |
| Marina | O que testar como oferta associada? | Categorias e recomendações | Similaridade de público não é propensão nem causalidade. |
| Sr. Almir | Qual é o menor dia do POS quando zeros entram no denominador? | Média por dia da semana | Rede agregada não substitui análise por loja ou margem. |
| Sr. Almir | Quanto o baseline errou e em qual direção? | Previsão × realizado | O teste mede erro histórico; não define quantidade de compra. |
| Gabriel | Quais fontes, regras e checks sustentam cada número? | Linhagem, fontes e qualidade | Checks estruturais não resolvem semântica de negócio. |
| Gabriel | Qual decisão continua insegura? | Premissas e alertas | Status e data de corte podem mudar materialmente os rankings. |

Os chips **Perguntas que esta visão responde** levam diretamente à seção
correspondente da aba ativa.

## Premissas que devem ser ditas em voz alta

- **Todos os status entram:** `paid`, `confirmed`, `cancelled` e `draft` são
  mantidos porque não há regra aprovada de elegibilidade.
- **Valor registrado não é receita reconhecida:** `orders.total` é somado como
  está no arquivo. Não chamar a métrica de lucro, margem ou caixa; a moeda também
  precisa ser confirmada.
- **Sem PII:** o JSON, o dashboard, o CSV exportado e o PDF usam somente
  agregados e aliases de clientes.
- **Há datas futuras no snapshot:** a fonte alcança 31/12/2026, posterior à data
  de geração desta entrega. O período deve ser tratado como cobertura do arquivo,
  não como estado operacional corrente, até que o corte seja validado.
- **POS é rede agregada:** o menor dia da rede não deve ser aplicado
  automaticamente a cada loja.
- **Modelos são sinais:** previsão é baseline; recomendação é similaridade por
  co-compra. Nenhum dos dois autoriza ação automática.

## Como usar os controles

### Baixar recorte CSV

1. escolha uma das quatro visões: **Ponte de Comando**, **Marina**,
   **Sr. Almir** ou **Gabriel**;
2. clique em **Baixar recorte CSV**;
3. abra o arquivo baixado e confira as colunas
   `secao;dimensao;periodo;metrica;valor;detalhe`.

O recorte é montado no navegador apenas com os agregados da visão ativa. O nome
segue o padrão `lh-nautical-<id-da-visão>-<data-do-snapshot>.csv`, usando
`command`, `marina`, `almir` ou `gabriel`; o separador é ponto e vírgula e o
arquivo é codificado em UTF-8 com BOM. Trocar de aba antes do download muda o
conteúdo exportado.

### Gerar mini-relatório

1. deixe aberta a visão que deseja registrar;
2. clique em **Gerar mini-relatório**;
3. no diálogo nativo de impressão, revise a prévia e escolha imprimir ou
   **Salvar como PDF**.

O modo de impressão inclui apenas a persona ativa, seu cabeçalho, período,
cards e gráficos; sidebar, perguntas e controles ficam ocultos. O recurso chama
a impressão do navegador: não existe geração em backend nem nome de arquivo
garantido. O PDF executivo completo continua sendo o arquivo de oito páginas
linkado no início deste documento.

## Regeneração e execução local

Execute a partir da raiz do projeto para manter JSON e PDF sincronizados:

```bash
python3 scripts/build_dashboard_data.py
python3 scripts/generate_executive_report.py
```

Os comandos atualizam, respectivamente:

- `dashboard/public/data/dashboard.json`;
- `deliverables/LH_Nautical_Resumo_Executivo.pdf`.

Para abrir o dashboard em desenvolvimento, use Node.js 20.19 ou superior:

```bash
cd dashboard
npm install
npm run dev
```

O Vite informa no terminal o endereço **local** da sessão. Para validar a versão
estática antes da entrega:

```bash
cd dashboard
npm run typecheck
npm run build
npm run preview
```

`npm run preview` também é uma prévia local; não comprova publicação externa.

## Checklist antes da apresentação

- regenerar primeiro o JSON e depois o PDF;
- confirmar que o dashboard mostra o período de 01/01/2020 a 31/12/2026;
- testar a navegação e os chips nas quatro visões;
- baixar um CSV de cada visão e conferir que não contém PII;
- abrir a prévia do mini-relatório em cada aba;
- conferir as oito páginas do PDF e manter a ressalva “valor registrado”;
- não apresentar URL pública ou implantação como concluída sem evidência externa.
