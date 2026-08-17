# LH Nautical — Da base à decisão

Dashboard analítico desenvolvido em React para apresentar os resultados do
desafio sob três perspectivas: crescimento, operação e confiança nos dados.

**Dashboard publicado:** https://desafioindicium.eumoas.workers.dev

## Arquitetura

```text
CSVs de origem
      ↓
scripts/build_dashboard_data.py
      ↓
public/data/dashboard.json (somente agregados, sem identificadores)
      ↓
React + TypeScript + Tailwind + Recharts
```

Os CSVs versionados pertencem ao cenário sintético do desafio. Mesmo assim, o
navegador não os recebe: o arquivo publicado contém apenas métricas agregadas e
identificadores técnicos necessários para a análise.

## Gerar os dados

Na raiz do projeto:

```bash
python3 scripts/build_dashboard_data.py
```

## Executar localmente

É necessário Node.js 20.19 ou mais recente.

```bash
cd dashboard
npm install
npm run dev
```

## Validar e gerar a versão de produção

```bash
npm run typecheck
npm run build
npm run preview
```

O conteúdo estático será criado em `dashboard/dist`. Para publicar no Worker
configurado em `wrangler.jsonc`:

```bash
npm run deploy
```

Na integração do Cloudflare Workers Builds, o diretório raiz é `dashboard`, o
comando de build é `npm run build` e o comando de deploy é
`npx wrangler deploy`.

## Premissas importantes

- A regra literal do desafio considera todos os status de pedido.
- `orders.total` é apresentado como valor registrado, não como receita
  reconhecida ou lucro.
- A recomendação mede afinidade de público, não probabilidade de compra nem
  complementaridade causal.
- A previsão é um baseline de média móvel, não uma ordem automática de compra.
- Nenhum dado pessoal de cliente é publicado pelo dashboard.
