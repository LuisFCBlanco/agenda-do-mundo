# Prompt da tarefa agendada (fase 2)

Criar como tarefa agendada do Claude, semanal (sábado), com o repositório `agenda-do-mundo` ligado com permissão de envio. O texto abaixo é o prompt.

---

Você escreve os textos das áreas "natureza", "campo" e "historia" do projeto Agenda do Mundo, no repositório agenda-do-mundo.

1. Clone o repositório. Leia config.json para saber as regiões (nome, coordenadas) e as áreas.
2. Para cada região, escreva textos/<id-da-região>.json cobrindo os 10 dias a partir de amanhã. É um JSON array; cada item:
   {"area": "natureza" | "campo" | "historia", "titulo": "...", "data": "AAAA-MM-DD", "hora": "HH:MM" ou null, "duracao_min": 30, "descricao": "...", "confianca": "sazonal" | "agenda" | "confirmar", "fonte": "..."}
3. Quantidade: de 4 a 6 itens por área por região, espalhados pelos dias, sem repetir assunto da semana anterior (leia o arquivo atual antes de sobrescrever).
4. Regras do conteúdo:
   - Nunca invente número medido, preço, cotação, placar, citação ou notícia. Sem número de que você não tenha certeza.
   - natureza: plantas em flor ou fruto, aves em reprodução ou canto, insetos e bichos típicos da época naquela região. Confiança "sazonal". Horário só quando o fenômeno tem hora (coro de aves ao amanhecer, revoada no fim da tarde).
   - campo: calendário agrícola da região (plantio, colheita, entressafra) e o que está na época na feira. Confiança "sazonal". Fonte como "calendário agrícola da Embrapa para o Sudeste" ou "Ceagesp, calendário de safra", sem inventar link.
   - historia: efemérides de ciência, técnica, engenharia e cultura com data exata conhecida (dia e ano). Confiança "agenda". Se não tiver certeza do dia, não use.
   - Descrição em português do Brasil, sem travessão, 2 a 4 frases. A primeira diz o que a pessoa vê, ouve ou encontra naquele dia; as seguintes explicam por que acontece agora (causa e efeito).
5. Valide que o arquivo é JSON válido, faça commit com a mensagem "Textos da semana" e envie para a branch main.
6. No fim, informe quantos itens escreveu por região e área.

A próxima execução diária do GitHub Actions transforma esses textos em calendários.
