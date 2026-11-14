# Agenda do Mundo

Calendários assináveis com o que acontece no mundo ao redor de cada região: o céu, a natureza, a economia, as culturas, a saúde e a história, para 47 cidades. A pessoa escolhe as áreas no site e assina cada uma no Google Agenda, iPhone ou Outlook. Ninguém faz login e nada é gravado na agenda de ninguém.

## Como funciona

- `gerar.py` monta um `.ics` por lugar e área, um por grupo e um com tudo, dentro de `docs/feeds/`, e o `docs/catalogo.json` que o site lê. Esses arquivos não ficam no repositório: são gerados e publicados direto no site.
- O GitHub Actions (`.github/workflows/diario.yml`) roda todo dia às 5h17 e a cada mudança nos textos, e publica no GitHub Pages (fonte: GitHub Actions).
- Áreas calculadas não precisam de internet. Áreas com dados ao vivo buscam a fonte; se ela falhar, o calendário mantém os dados da geração anterior, lidos do próprio site, e a falha vira uma issue com o rótulo `falha`.
- Cada área tem um emoji, que entra no título dos eventos.

## Link pessoal (opcional)

`servico/worker.js` é um serviço pequeno para o Cloudflare Workers (plano gratuito). Com ele, a pessoa marca as áreas no site e recebe um link só dela; quando muda as marcações, o mesmo link passa a entregar o novo conjunto, sem assinar de novo e sem duplicar. Para ligar: criar o Worker e um KV chamado `AGENDA` (`npx wrangler kv namespace create AGENDA`, colar o id em `servico/wrangler.toml`, `npx wrangler deploy`) e pôr o endereço em `servico_url` no `config.json`. Sem ele, o site oferece tudo num calendário, um por grupo, ou área por área.

## Mudar regiões e áreas

`config.json` lista as regiões (nome, coordenadas, estado) e as áreas. Uma região nova é uma linha nova com latitude e longitude.

## Pontos em aberto

- Banco Central, Open-Meteo e eBird foram testados com respostas no formato documentado de cada um, não contra os servidores reais. O primeiro "Run workflow" é o teste real.
- O link "Assinar no Google" usa um formato que o Google não documenta oficialmente, mas que é amplamente usado. "Copiar link" funciona sempre.
- Em repositório público, o GitHub pode pausar tarefas agendadas depois de 60 dias sem atividade. Se chegar um e-mail avisando, basta reativar em Actions.

## Textos escritos pelo Claude

As áreas de natureza, safra, cultura regional, história, materiais, esporte, telas, energia e agro vêm de `textos/<escopo>/*.json` (`brasil` ou uma das cinco regiões), escritos por quatro tarefas agendadas do Claude que pesquisam na web. As regras estão em `tarefas/REGRAS.md`, o passo a passo em `tarefas/PROCEDIMENTO.md`, e `validar.py` confere cada arquivo antes do commit.

## Escopos

- **local** (cada cidade de `config.json`): Lua, céu, sol, estações, clima, qualidade do ar, aves do eBird, feriados, calendário védico, Ayurveda.
- **regional** (Norte, Nordeste, Centro-Oeste, Sudeste, Sul): natureza, safra, cultura.
- **nacional** (`brasil`): economia, investidor, agro, energia, culturas do mundo, saúde pública, história, materiais, datas, esporte, telas.
