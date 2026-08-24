# Research: Revisão Humana de Transações

## Pending review = `confidence != 'high'`, sem condição especial pra transferência

- **Decision**: um item está pendente de revisão se, e somente se, `confidence != 'high'`. Não existe uma
  condição OR separada para candidatos a transferência.
- **Rationale**: pela feature 002, `category = "Transferência interna"` só é atribuída com `confidence = medium` —
  nunca `high`. Logo, todo candidato a transferência já está coberto pela condição `confidence != 'high'`; uma
  condição adicional seria redundante. Simplifica FR-001 e a query de `list_pending_review`.
- **Alternatives considered**: `WHERE confidence != 'high' OR category = 'Transferência interna'` — rejeitado por
  ser logicamente redundante dado o invariante estabelecido na feature 002.

## Múltiplas interrupções em um único node

- **Decision**: `nodes/review.py` consulta os itens pendentes do mês a cada execução/retomada, e itera sobre eles
  chamando `interrupt(payload)` uma vez por item, dentro de um laço `for`. A resposta do usuário (`Command(resume=
  ...)`) é validada e persistida imediatamente antes de passar para o próximo item do laço.
- **Rationale**: é o padrão recomendado pelo próprio LangGraph para HITL com múltiplas perguntas sequenciais numa
  única execução de node — ao retomar, o node é reexecutado do início, e cada `interrupt()` já respondido devolve
  o valor de resume gravado no checkpoint, sem re-perguntar. Como a lista de pendentes é consultada no banco a
  cada execução (não capturada uma vez em memória), itens já decididos em uma retomada anterior simplesmente não
  aparecem mais na lista — FR-007 ("não perguntar de novo") sai de graça da combinação
  checkpointer + consulta sempre fresca ao banco.
- **Alternatives considered**: um node por item pendente, com uma aresta condicional que decide se volta pro
  mesmo node ou segue adiante — rejeitado por adicionar complexidade de grafo (Princípio I) sem ganho real sobre
  o laço dentro de um único node.

## Validação de categoria dentro do node, não na CLI

- **Decision**: a validação da categoria/subcategoria informada manualmente (FR-009) acontece dentro de
  `nodes/review.py`, usando o mesmo `Taxonomy` da feature 002. Se a resposta for inválida, o node chama
  `interrupt()` de novo para o **mesmo** item, agora com uma mensagem de erro no payload, sem avançar para o
  próximo item.
- **Rationale**: mantém a CLI genérica — ela só exibe o payload que o node manda e devolve uma linha de texto,
  sem conhecer regras de categorização. Isso preserva o Princípio II (regra de negócio fora da camada de
  interface) e permite testar a validação sem terminal nenhum.
- **Alternatives considered**: validar na CLI antes de enviar o resume — rejeitado porque duplicaria a lógica de
  taxonomia em duas camadas, e a CLI passaria a conhecer regra de negócio que não é dela.

## Formato da resposta do usuário

- **Decision**: mesmo formato de texto usado pelo `llm_categorizer` (feature 002): `"categoria|subcategoria"`
  (subcategoria vazia se não houver), mais duas palavras-chave especiais: `aceitar` (mantém a sugestão como está)
  e `confirmar` (só para candidatos a transferência — mantém "Transferência interna").
- **Rationale**: reaproveita um formato e um parser já validados na feature anterior, em vez de inventar um novo
  protocolo de resposta — Princípio I.
- **Alternatives considered**: prompt interativo item por item (ex.: biblioteca de TUI com menus) — rejeitado como
  over-engineering para uma CLI de validação de fluxo (BRD seção 3: "Foco em validar o fluxo do agente antes de
  investir em UI").

## Checkpointer

- **Decision**: `langgraph-checkpoint-sqlite` (`SqliteSaver`), apontando para o mesmo arquivo `.db` usado por
  `db/repository.py`. `thread_id` do grafo é o `month_ref` (ex.: `"2026-08"`), conforme já definido no BRD.
- **Rationale**: é a peça que torna FR-006/FR-007/SC-002 possíveis — sem checkpointer persistente, qualquer
  interrupção perderia o progresso da sessão. BRD já planeja a troca futura para
  `langgraph-checkpoint-postgres` "mesma interface", então usar a variante SQLite agora não compromete o
  Princípio IV.
- **Alternatives considered**: checkpointer em memória (`MemorySaver`) — rejeitado porque não sobrevive a uma
  interrupção real de processo, violando diretamente SC-002.

## Estratégia de testes

- **Decision**: testes chamam o grafo compilado via `.invoke()`/`.stream()` com um `thread_id` de teste, capturam
  o payload do primeiro `interrupt()`, respondem com `Command(resume=...)`, e repetem até o grafo terminar —
  tudo isso dentro do processo de teste, sem subprocess nem terminal real.
- **Rationale**: mantém a suíte determinística e rápida, alinhado à constituição.
- **Alternatives considered**: testar `interface/cli.py` fim a fim simulando stdin — mantido como um teste
  adicional leve (smoke test), não como a forma principal de testar a lógica de decisão do node.
