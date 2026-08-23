# Research: Ingestão de Extratos Bancários

Nenhum marcador `NEEDS CLARIFICATION` restou no Technical Context — o BRD (`docs/brd-financial-planner-agent.md`,
seção 6.3) já valida o formato dos dois bancos a partir de exports reais. Este documento registra as decisões
técnicas necessárias para implementar as decisões de negócio já tomadas.

## Detecção de linhas de transação

- **Decision**: testar cada linha do arquivo contra um regex de data no início da linha (`^\d{2}/\d{2}/\d{4};`);
  só linhas que batem viram transação candidata.
- **Rationale**: validado contra arquivo real do Bradesco (54 linhas totais → 42 linhas de transação válidas),
  resolve de forma robusta metadado inicial, header duplicado no meio do arquivo ("Últimos Lancamentos") e rodapé
  "Total" sem precisar mapear a estrutura exata linha a linha.
- **Alternatives considered**: `skiprows` fixo por banco — rejeitado por ser frágil a variações de tamanho de
  metadado e por não lidar com o header duplicado no meio do arquivo do Bradesco.

## Detecção automática do banco de origem

- **Decision**: inspecionar a estrutura de colunas do header antes de aplicar o parser específico — presença de
  colunas `Crédito (R$)` e `Débito (R$)` separadas + `Docto.` identifica Bradesco; presença de coluna única `Valor`
  com sinal + linhas de metadado no formato Inter (título/conta/período/saldo) identifica Inter.
- **Rationale**: os dois formatos são estruturalmente distintos o suficiente (nº e nome de colunas) para não
  precisar de heurística ambígua; se nenhum dos dois padrões é reconhecido, o arquivo é rejeitado (FR-001, FR-009).
- **Alternatives considered**: detecção por nome/extensão de arquivo — rejeitado porque o usuário exporta os
  arquivos manualmente e não há garantia de convenção de nome.

## Normalização de valor e data

- **Decision**: valor no formato brasileiro (`1.645,20`) é normalizado removendo separador de milhar (`.`) e
  trocando `,` por `.` antes de converter para número; data `DD/MM/AAAA` é parseada com formato explícito
  (equivalente a `strptime("%d/%m/%Y")`), nunca inferência automática de formato.
- **Rationale**: inferência automática de formato de data (ex.: `dateutil` sem formato explícito) é ambígua para
  datas como `01/02/2026` (poderia ser lido como mês/dia); formato explícito elimina essa classe de erro.
- **Alternatives considered**: usar `locale` do sistema para parsing pt-BR — rejeitado por depender de configuração
  do ambiente de execução, quebrando o Princípio de Simplicidade Pragmática sem necessidade real.

## Hash de deduplicação

- **Decision**: hash determinístico (ex.: SHA-256) sobre a concatenação normalizada de
  `date + description_raw + amount + account`, calculado após a normalização de valor/data (não sobre o texto cru
  do CSV).
- **Rationale**: calcular sobre valores já normalizados garante que a mesma transação gere o mesmo hash mesmo que
  aaparência textual bruta varie ligeiramente entre exports (ex.: espaço extra); atende FR-006 e Princípio VII da
  constituição.
- **Alternatives considered**: usar `Docto.` do Bradesco como identificador nativo — rejeitado porque o Inter não
  tem equivalente (BRD 6.3), então não serve como estratégia única para os dois bancos.

## Checagem de saldo como sanidade

- **Decision**: comparar, em ordem cronológica dentro do arquivo, o saldo declarado de uma linha contra
  `saldo anterior ± valor da transação atual`; divergências (fora de uma tolerância de arredondamento, ex.:
  R$ 0,01) geram um aviso reportado ao usuário (FR-009), mas não abortam a importação das transações já
  reconhecidas corretamente.
- **Rationale**: é uma checagem de qualidade de dado, não uma regra de negócio que impede o fluxo — o objetivo é
  visibilidade (Princípio de nunca falhar silenciosamente), não bloqueio automático de todo o arquivo por causa de
  uma linha suspeita.
- **Alternatives considered**: abortar a importação inteira em caso de qualquer divergência de saldo — rejeitado
  por ser desproporcional; um único erro de leitura de linha não deveria descartar um mês inteiro de transações
  corretas.

## Estratégia de testes

- **Decision**: fixtures pequenas (2-3 linhas) por banco cobrindo o caso feliz e os casos de borda documentados na
  spec (BOM, header duplicado, `Descrição` vazia, linha em branco, rodapé "Total"); testes determinísticos, sem
  rede nem LLM.
- **Rationale**: alinhado à seção "Padrões de Teste" da constituição; parsers são puros o suficiente para não
  precisar de mocks.
- **Alternatives considered**: usar os arquivos reais completos como fixture de teste — rejeitado porque dado real
  nunca entra no repositório (constituição, seção "Proteção de Dados Sensíveis").
