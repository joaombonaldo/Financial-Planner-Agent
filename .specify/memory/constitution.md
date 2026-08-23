<!--
Sync Impact Report
- Version change: (template) → 1.0.0
- Modified principles: n/a (initial ratification)
- Added sections:
  - Core Principles: I. Simplicidade Pragmática, II. Nodes Isolados de Infraestrutura,
    III. LLM Trocável por Abstração, IV. Persistência Portável, V. Revisão Humana
    Obrigatória para Decisões Sensíveis, VI. Confiança Categórica, VII. Deduplicação
    Determinística
  - Proteção de Dados Sensíveis
  - Padrões de Teste
  - Fora de Escopo (Fase Atual)
  - Governance
- Removed sections: none (initial version)
- Follow-up TODOs: none
-->

# Financial Planner Agent Constitution

## Core Principles

### I. Simplicidade Pragmática
Este é um projeto pessoal de aprendizado de agentes de IA (LangGraph), não um produto
comercial. Toda decisão de design DEVE ser avaliada pelo critério "meio-termo, sem
exagero": nem o atalho que compromete a arquitetura, nem a engenharia excessiva que
antecipa requisitos hipotéticos. Abstrações, camadas ou padrões só são justificados
quando resolvem uma necessidade concreta já identificada no projeto — não uma
possibilidade futura.

### II. Nodes Isolados de Infraestrutura
Nodes do grafo (LangGraph) NUNCA acessam banco de dados, LLM ou arquivos diretamente.
Todo acesso a infraestrutura passa por módulos dedicados (ex.: `db/repository.py`,
cliente de LLM abstraído). Isso preserva a direção de dependência de clean architecture
sem exigir interfaces formais (Protocol/ABC) — a separação é por convenção de módulo,
não por contrato de tipos. Rationale: mantém os nodes testáveis e substituíveis sem
impor a cerimônia de uma arquitetura hexagonal completa, compatível com o Princípio I.

### III. LLM Trocável por Abstração
O LLM é acessado via abstração trocável (`init_chat_model` ou equivalente). Hoje é
Ollama local com Qwen2.5; a implementação DEVE permitir troca para Claude, OpenAI ou
outro provedor sem alterar código de nodes. Rationale: o objetivo de aprendizado inclui
avaliar categorização entre modelos locais e externos.

### IV. Persistência Portável
SQLite é o banco da Fase 1, mas todo acesso a dados DEVE permanecer portável para
Postgres/Supabase: usar SQL padrão (evitar extensões específicas do SQLite) e um
checkpointer com interface equivalente em ambos os backends.

### V. Revisão Humana Obrigatória para Decisões Sensíveis
Toda decisão financeira sensível — categorização de confiança baixa ou média, detecção
de transferência entre contas próprias — DEVE passar por revisão humana via
`interrupt()`. Isso é obrigatório mesmo quando o resultado parece óbvio; a automação
completa dessas decisões é NÃO permitida nesta fase. Rationale: erros de categorização
financeira têm custo de correção maior que o custo de uma confirmação humana.

### VI. Confiança Categórica
A confiança de categorização é representada de forma categórica (`high`/`medium`/`low`),
nunca numérica. Rationale: LLMs não produzem probabilidades calibradas de forma
confiável; expor um número (ex. "87%") passaria uma precisão que não existe.

### VII. Deduplicação Determinística
Transações usam hash de deduplicação (data + descrição + valor + conta) para evitar
duplicação em reimportações. A deduplicação é determinística e não depende de
julgamento do LLM.

## Proteção de Dados Sensíveis

Nenhum dado financeiro real (extratos, categorias ou metas pessoais, banco `.db`) entra
no repositório em nenhuma hipótese. O `.gitignore` DEVE estar configurado cobrindo esses
artefatos antes do primeiro commit do projeto. Qualquer script, teste ou fixture que
precise de dados de exemplo DEVE usar dados sintéticos.

## Padrões de Teste

- Parsers têm testes unitários determinísticos com fixtures pequenas por banco.
- Existe um golden set de transações com categoria correta conhecida, usado para medir
  acurácia de categorização — crítico ao trocar de LLM local para um provedor externo.
- O grafo é testável com LLM mockado, sem depender do Ollama rodando.

## Fora de Escopo (Fase Atual)

Os itens abaixo são explicitamente NÃO perseguidos nesta fase do projeto: integração
bancária automática (open banking), multiusuário/autenticação, app mobile, alertas em
tempo real. Propostas que introduzam esses itens DEVEM ser tratadas como uma nova fase,
não como extensão incremental do escopo atual.

## Governance

Esta constituição tem precedência sobre qualquer outra prática ou convenção adotada no
projeto. Alterações exigem:

1. Registro da mudança nesta constituição, com atualização do Sync Impact Report no
   topo do arquivo.
2. Versionamento semântico:
   - MAJOR: remoção ou redefinição incompatível de princípios existentes.
   - MINOR: adição de novo princípio ou expansão material de uma seção.
   - PATCH: esclarecimentos, correções de texto, refinamentos não semânticos.
3. Atualização da data de "Last Amended" para a data da mudança.

Specs, planos e tasks gerados pelos comandos `/speckit-*` DEVEM estar em conformidade
com os princípios aqui definidos; qualquer desvio precisa de justificativa explícita no
artefato correspondente.

**Version**: 1.0.0 | **Ratified**: 2026-08-23 | **Last Amended**: 2026-08-23
