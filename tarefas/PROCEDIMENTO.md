# Procedimento das tarefas semanais

Cada tarefa agendada recebe no prompt qual arquivo de tarefa seguir (`nacional.md`, `natureza.md` ou `regional.md`) e, quando for o caso, quais regiões.

1. Anexe o repositório com a ferramenta add_repo (owner `LuisFCBlanco`, repo `agenda-do-mundo`, access `push`) e clone como ela indicar.
2. Leia `tarefas/REGRAS.md` e o arquivo da sua tarefa.
3. **Falhas.** Só na tarefa nacional: liste as issues abertas com o rótulo `falha` (`gh api "repos/LuisFCBlanco/agenda-do-mundo/issues?labels=falha&state=open"` e os comentários) e as últimas execuções do workflow. Se uma fonte falhou vários dias seguidos e a causa estiver clara (API mudou formato ou endereço), faça a correção mínima em `gerar.py`, teste com `python3 gerar.py` e inclua no commit. Se não estiver clara, só descreva no resumo. Nunca feche issue à mão.
4. Pesquise na web o que for preciso e escreva os arquivos indicados, cobrindo os 8 dias a partir de amanhã. Leia o arquivo atual antes de sobrescrever, para não repetir assunto da semana anterior.
5. Rode `python3 validar.py <arquivos>` até sair `ok`.
6. Commit só dos arquivos da sua tarefa (e da correção do passo 3, se houver), com a mensagem `Textos da semana: <tarefa>`. Antes do push: `git pull --rebase origin main` (outras tarefas escrevem outros arquivos no mesmo dia). Depois: `git -c push.negotiate=true push origin main`.
7. Dispare a geração: `gh api -X POST repos/LuisFCBlanco/agenda-do-mundo/actions/workflows/diario.yml/dispatches -f ref=main`
8. Termine com um resumo curto: itens por arquivo e área, o que buscou e não achou, falhas encontradas e o que fez.
