# Como contribuir

A Agenda do Mundo cresce de dois jeitos.

## Sugerir uma cultura

Abra uma [sugestão](https://github.com/LuisFCBlanco/agenda-do-mundo/issues/new?template=sugerir-cultura.yml). Ela não entra sozinha: o mantenedor decide o que vira área.

## Escrever a agenda de uma cultura que você conhece

1. Leia `tarefas/REGRAS.md`. São as regras de escrita: a cena primeiro, o porquê, número só medido, fonte específica, sem travessão.
2. Crie ou edite um arquivo em `textos/<escopo>/<seu-arquivo>.json`. O escopo é `brasil` para áreas nacionais e mundiais, ou uma das regiões (`norte`, `nordeste`, `centro-oeste`, `sudeste`, `sul`). O campo `area` de cada item tem que ser uma área que existe em `config.json`.
3. Rode `python3 validar.py textos/<escopo>/<seu-arquivo>.json` até sair `ok`.
4. Abra um pull request.

Toda contribuição passa por duas checagens: a automática (as regras de escrita e um teste do gerador, que rodam sozinhos no pull request) e a do mantenedor, que lê e aprova antes de entrar. Nada é publicado sem as duas.

Uma área nova (que ainda não existe em `config.json`) precisa primeiro de uma sugestão aceita.
