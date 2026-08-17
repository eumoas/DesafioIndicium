# Dados do desafio

Este diretório concentra as fontes utilizadas na solução. Os 24 arquivos CSV
foram fornecidos como um snapshot sintético e fictício do cenário LH Nautical;
não representam pessoas, empresas ou operações reais.

## Organização

```text
data/
├── README.md
└── raw/          # arquivos recebidos, preservados sem tratamento
```

`raw/` é uma zona de entrada imutável: nomes, cabeçalhos, valores, encoding e
granularidade devem permanecer como recebidos. Correções, filtros e agregações
não devem sobrescrever as fontes. Os resultados reproduzíveis ficam em
[`../outputs/`](../outputs/), enquanto o contrato agregado do dashboard fica em
[`../dashboard/public/data/dashboard.json`](../dashboard/public/data/dashboard.json).

## Inventário do snapshot

- 24 arquivos;
- 433.424 registros, sem contar os cabeçalhos;
- aproximadamente 36 MB;
- cobertura temporal observada no conjunto analítico: 2020 a 2026.

| Arquivo | Registros | Conteúdo principal |
|---|---:|---|
| `addresses.csv` | 3.998 | Endereços de clientes |
| `attributes.csv` | 8 | Atributos de produto |
| `brands.csv` | 12 | Marcas |
| `categories.csv` | 14 | Categorias de produto |
| `customers.csv` | 2.000 | Cadastro de clientes |
| `employees.csv` | 15 | Cadastro de colaboradores |
| `fiscal_invoices.csv` | 34.365 | Notas fiscais |
| `goods_receipt_items.csv` | 4.733 | Itens de recebimento |
| `goods_receipts.csv` | 1.548 | Recebimentos de mercadoria |
| `locations.csv` | 6 | Lojas e locais de estoque |
| `order_items.csv` | 147.320 | Itens dos pedidos |
| `orders.csv` | 48.998 | Pedidos |
| `payments.csv` | 53.546 | Pagamentos |
| `product_suppliers.csv` | 1.520 | Relações produto-fornecedor |
| `product_variants.csv` | 1.009 | Variantes e SKUs |
| `products.csv` | 500 | Produtos |
| `purchase_order_items.csv` | 6.059 | Itens de ordens de compra |
| `purchase_orders.csv` | 2.000 | Ordens de compra |
| `return_items.csv` | 1.384 | Itens devolvidos |
| `returns.csv` | 980 | Devoluções |
| `stock_levels.csv` | 6.054 | Posições de estoque |
| `stock_movements.csv` | 115.312 | Movimentações de estoque |
| `suppliers.csv` | 25 | Cadastro de fornecedores |
| `variant_attribute_values.csv` | 2.018 | Valores de atributos das variantes |
| **Total** | **433.424** | **24 fontes** |

## Reprodução

Execute os comandos a partir da raiz do repositório:

```bash
python3 scripts/schema.py data/raw -o schema.sql
python3 scripts/load.py data/raw
python3 scripts/questao_6_1.py data/raw --output-directory outputs
python3 scripts/questao_7_1.py data/raw --output-directory outputs
python3 scripts/build_dashboard_data.py data/raw --output dashboard/public/data/dashboard.json
```

Os scripts tratam `data/raw` como diretório de entrada. Arquivos de saída não
devem ser copiados para essa pasta, pois seriam confundidos com novas tabelas
pelos processos que descobrem todos os CSVs do diretório.

## Privacidade, licença e uso responsável

Embora os valores sejam sintéticos, algumas colunas imitam dados pessoais ou
confidenciais — por exemplo, CPF/CNPJ, inscrição estadual, e-mail, telefone e
endereço. Elas devem ser tratadas com a mesma cautela de estrutura que seria
aplicada a dados reais: não são publicadas no dashboard, no PDF ou nos recortes
exportados.

O caráter sintético não concede, por si só, uma licença de redistribuição. A
publicação deste snapshot deve permanecer condicionada às regras do desafio e
à autorização de quem forneceu os arquivos. Para uma base real, seria
necessário retirar `data/raw` do Git, aplicar controles de acesso e definir
base legal, retenção e descarte.

## Política de alteração

- não editar manualmente os CSVs em `raw/`;
- não substituir valores nulos, corrigir caracteres ou remover registros nessa
  camada;
- registrar um novo snapshot separadamente caso outra extração seja recebida;
- regenerar `schema.sql`, `outputs/`, dashboard e relatório após qualquer nova
  versão aprovada das fontes.
