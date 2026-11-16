# Regras de escrita da Agenda do Mundo

Valem para todas as tarefas semanais que escrevem em `textos/`. O calendário é público: existe para qualquer pessoa se situar no mundo que está acontecendo ao redor dela.

## Formato

Cada arquivo é uma lista JSON. Cada item:

```json
{"area": "avifauna", "titulo": "...", "data": "AAAA-MM-DD", "hora": "HH:MM" ou null, "duracao_min": 30,
 "descricao": "...", "confianca": "sazonal" | "agenda" | "confirmar", "fonte": "..."}
```

- `hora` é a do fenômeno no mundo, em horário de Brasília (canto ao amanhecer 05:30, revoada no fim da tarde 18:00, jogo 16:00). Sem hora própria, `null`.
- `confianca`: `sazonal` para o que é típico da época e da região; `agenda` para data fixa e certa (efeméride com ano, feriado, jogo confirmado na tabela oficial); `confirmar` para data provável que ainda pode mudar.
- Antes do commit, rode `python3 validar.py <arquivo>` e corrija até sair `ok`.

## Em que dia o evento entra

- **O que tem data marcada no futuro** (jogo, estreia, divulgação, lançamento, festa, efeméride) entra no dia em que acontece.
- **O que já aconteceu** (cotação fechada, descoberta publicada, decisão tomada, venda de empresa) entra no dia em que aconteceu, mesmo que seja antes de hoje, desde que nos últimos 7 dias. Nunca ponha um fato passado num dia futuro: quem abre a agenda na quinta não pode ler como novidade um número da semana retrasada.
- Fato com mais de 7 dias só entra se for o dado mais recente que existe (boletim mensal, por exemplo), e o título diz de quando é.
- **Natureza e safra** (confiança `sazonal`) continuam espalhadas pelos 8 dias à frente.

## Cobertura

Cada área tem uma quantidade pedida no arquivo da tarefa. Se entregar menos, o resumo final diz qual área ficou abaixo e por quê (não achou fonte, bateu o teto). Área vazia sem explicação é erro.

## Como escrever

1. **A cena abre o evento.** A primeira frase descreve o que uma pessoa vê, ouve ou encontra naquele dia naquela região, em linguagem de rua: a lâmpada cheia de bicho de asa, o canto antes de o sol nascer, o preço do tomate na banca. Tem que ser verdade para aquele dia e lugar. Se não existe cena observável, abra pelo fato.
2. **Depois, o porquê.** Explique por que acontece agora: causa e efeito, a física, a química, a biologia ou a economia por trás.
3. **Número só medido.** Quando existir, um número medido com a origem dita (percentual do reservatório, cotação de fechamento, quilômetros da migração). Nunca estime número para ter número.
4. **O que é novo neste ano.** Em fenômeno que se repete (florada, safra, reservatório, preço sazonal), quando houver dado deste ano, diga o que mudou em relação ao ano anterior ou à média. Sem dado, não escreva sobre isso.
5. **Som.** Em ave, anfíbio ou inseto que canta, procure no xeno-canto (xeno-canto.org) uma gravação da espécie e ponha o link na fonte com a licença. Se a licença tiver NC ou ND, escreva ao lado "só para ouvir".
6. **Escreva confortável.** Sem aviso de versão anterior, sem parágrafo de grau de certeza, sem rótulo de seção dentro do texto. Firmeza onde há firmeza; ressalva só quando muda o que a pessoa faria.
7. **A ordem do texto varia.** Se dois eventos seguidos se desenvolvem do mesmo jeito, o segundo está errado. Lido em voz alta, tem que soar como alguém contando algo interessante, não como ficha técnica.

## O que não pode

- Travessão (— ou –), em título ou texto. Use vírgula, parênteses ou dois pontos.
- Título começando com: Janela de, Período de, Início de, Pico de, Fim de.
- Fonte genérica ("estudos indicam", "literatura entomológica"). A fonte nomeia autor e ano, instituição e série de dados, ou órgão e data do boletim, e cobre o domínio do fato (nunca base de aves citada para planta).
- Inventar. Se buscou e não achou, não crie o evento; registre no resumo final o que buscou e onde.
- Notícia sem data e fonte verificáveis na web.
- Qualquer coisa pessoal sobre alguém: o calendário é para todos.
