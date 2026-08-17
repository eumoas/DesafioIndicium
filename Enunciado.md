Enunciado

## **Introdução**

Este desafio tem como objetivo avaliar sua aptidão para atuar na jornada de dados da LH Nautical, testando sua capacidade analítica, domínio técnico, visão de negócio e pragmatismo. Buscamos entender seu raciocínio de ponta a ponta: desde o tratamento de dados brutos e modelagem SQL até a geração de insights estratégicos e aplicação de lógica preditiva.

Não avaliamos apenas o código, mas a sua habilidade de transformar dados desorganizados em soluções que gerem valor real para a operação. Responda a todas as etapas com base no contexto fictício da LH Nautical descrito abaixo, seguindo as orientações do Tech Lead, Gabriel Santos.

## **Contexto Fictício**

#### **Sobre a Empresa**

A LH Nautical é uma empresa de varejo náutico com lojas físicas, armazéns e canal de e-commerce. Seus dados operacionais cobrem o período de 2020 a 2026 e registram o ciclo completo: catálogo de produtos, pedidos de venda, pagamentos, nota fiscal eletrônica, compras de fornecedores, movimentação de estoque e devoluções.

Você terá acesso a 24 arquivos CSV na pasta lh\_nautical\_csv/, representando o schema relacional da empresa. Sua missão é percorrer as etapas de um pipeline de dados real, da ingestão bruta à inteligência aplicada.

#### **Stakeholders Principais**

Durante o desafio, você interagirá com as necessidades de três perfis centrais da empresa: 

* **Gabriel Santos (Tech Lead):** O mentor técnico que valoriza a organização, a documentação e a clareza do raciocínio acima de códigos complexos.   
* **Marina Costa (Gerente de Negócios):** Focada em resultados práticos, margens de lucro e performance de vendas.   
* **Sr. Almir (Fundador):** Representa a visão old school; ele desconfia da "nuvem" e precisa ser convencido por dados sólidos e análises precisas. 

#### **Seu Objetivo**

Você acaba de receber um e-mail do Gabriel Santos, Tech Lead da LH Nautical. A empresa vai lançar uma campanha na semana que vem, mas os dados estão completamente desorganizados. Sua missão é limpar as bases, estruturar as tabelas e gerar os relatórios que a diretoria exige. Mas o Gabriel avisou: "Eu valorizo mais a organização e a explicação do que o código rodando sem eu entender nada."

Sua missão é atuar como o profissional de dados que transformará esse cenário. Você terá acesso a bases brutas (como o catálogo de produtos e históricos de vendas) e deverá realizar desde a limpeza e modelagem (Engenharia de Dados e SQL) até a geração de insights preditivos e sistemas de recomendação (Ciência de Dados e IA).

**Formato de Entrega:**

As entregas foram separadas em frentes de:

* EDA  
* Tratamento de dados  
* Análise de vendas  
* Análise de Clientes  
* Previsão de demandas  
* Sistemas de recomendações

E as solicitações estão organizadas nas questões desse desafio, **você deve interpretar as perguntas e responder cada questão com base nas suas análises seguindo as premissas obrigatórias.**  
Ao final do desafio, você **DEVERÁ** enviar um material complementar (painel/dashboard) com visualizações que ajudem a comunicar os principais resultados das análises realizadas no desafio. O envio é no formato que desejar e será realizada no campo 20 \- Espaço para adicionar arquivos (PDFs, Pbix, CSVs...).

**Sugestões de visuais para o dashboard/relatório:**

* Distribuição ou ranking de prejuízos por produto (questão 4\)  
* Gráfico dos clientes com maior lucro acumulado (questão 5\)  
* Vendas médias por dia da semana considerando dias sem venda (questão 6\)  
* Explorações adicionais relevantes

O objetivo é demonstrar como você organiza e comunica insights a partir dos dados.

Antes de qualquer análise, modelagem ou tomada de decisão, é fundamental entender o que existe nos dados. O Sr. Almir quer uma resposta simples: “Posso confiar nesses dados para tomar decisões?”

Sua missão é **realizar uma análise exploratória inicial nas tabelas** e responder perguntas básicas, porém críticas, sobre volume, distribuição e qualidade dos dados.

**Premissas obrigatórias**

* Utilize apenas a tabela "orders"  
* Não faça limpeza nem tratamento dos dados  
* Apenas observe, agregue e descreva  
* O código deve ser enviado em SQL

**Tarefas:** 

**Parte 1** \- Visão geral da tabela orders

Informe:

* Quantidade total de linhas  
* Intervalo de datas analisado (data mínima e máxima) da coluna created\_at

**Parte 2 \-** Análise de valores numéricos

Para a coluna "total", calcule:

* Valor mínimo  
* Valor máximo  
* Valor médio

**Parte 3** \- Interpretação

Responda de forma resumida:

Com base na análise exploratória realizada, escreva um breve diagnóstico sobre a confiabilidade da tabela o para análises futuras.

Comente sobre:

* possíveis outliers em "total",  
* qualidade dos dados (valores nulos ou inconsistentes),  
* e se você considera que o dataset está pronto para análises ou se exigiria tratamento prévio.

