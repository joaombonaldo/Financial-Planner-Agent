# Feature Specification: Ingestão de Extratos Bancários

**Feature Branch**: `001-ingest-extratos`

**Created**: 2026-08-23

**Status**: Draft

**Input**: User description: "Ingestão de extratos bancários (CSV) do Bradesco e do Inter, normalizando as transações para um schema único, detectando o banco de origem automaticamente e evitando duplicação em reimportações. Corresponde ao node `detect_and_parse` do grafo descrito no BRD."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Importar extrato de um banco suportado (Priority: P1)

Como usuário, quero apontar o sistema para um arquivo de extrato CSV exportado do Bradesco ou do Inter e obter as transações daquele mês em um formato único e normalizado, para que elas fiquem prontas para categorização, sem eu precisar limpar ou reformatar o arquivo manualmente.

**Why this priority**: Sem isso não existe projeto — é o primeiro node do grafo e todo o resto (categorização, revisão, orçamento, insights) depende de transações normalizadas e confiáveis.

**Independent Test**: Pode ser testado isoladamente fornecendo um arquivo de extrato real (ou fixture) de cada banco e verificando que a saída é uma lista de transações no schema normalizado, sem depender de nenhum outro node do grafo.

**Acceptance Scenarios**:

1. **Given** um arquivo de extrato do Bradesco (UTF-8 com BOM, colunas `Crédito (R$)`/`Débito (R$)` separadas, metadado na linha 1, bloco duplicado "Últimos Lancamentos" e linha de rodapé "Total"), **When** o sistema processa o arquivo, **Then** apenas as linhas de transação real são convertidas, na quantidade correta, e o banco de origem é identificado como Bradesco sem intervenção manual.
2. **Given** um arquivo de extrato do Inter (UTF-8 sem BOM, coluna única `Valor` com sinal, 4 linhas de metadado + linha em branco antes do header, `Descrição` vazia em algumas linhas), **When** o sistema processa o arquivo, **Then** todas as linhas de transação são convertidas corretamente, usando `Histórico` como descrição quando `Descrição` estiver vazia.
3. **Given** um valor no formato brasileiro (ex: `1.645,20`) e uma data no formato `DD/MM/AAAA`, **When** a transação é normalizada, **Then** o valor numérico e a data ficam em formato canônico único, igual para os dois bancos.

---

### User Story 2 - Reimportar um extrato sem duplicar transações (Priority: P2)

Como usuário, quero poder reimportar o mesmo arquivo (ou um novo export que sobreponha dias já processados) sem que as transações apareçam duplicadas, para poder reprocessar um mês com segurança sempre que precisar corrigir algo.

**Why this priority**: O Bradesco expõe dois blocos com potencial de sobreposição no mesmo arquivo, e reexportações futuras podem incluir dias já importados — sem isso os relatórios e o orçamento ficam incorretos silenciosamente.

**Independent Test**: Pode ser testado importando o mesmo arquivo duas vezes (ou dois arquivos com transações sobrepostas) e verificando que o número de transações armazenadas não aumenta na segunda importação.

**Acceptance Scenarios**:

1. **Given** um arquivo já importado com sucesso, **When** o mesmo arquivo é importado novamente, **Then** nenhuma transação nova é criada.
2. **Given** duas transações com mesma data, descrição, valor e conta vindas de seções diferentes do mesmo arquivo (ex: extrato principal + "Últimos Lancamentos" do Bradesco), **When** o arquivo é processado, **Then** apenas uma transação é mantida.

---

### User Story 3 - Ser avisado quando um arquivo não pôde ser processado corretamente (Priority: P3)

Como usuário, quero saber quando o parser não conseguiu interpretar corretamente um extrato (formato inesperado, linhas não reconhecidas, saldo que não fecha), para não tomar decisões financeiras baseadas em dados incompletos sem perceber.

**Why this priority**: É a rede de segurança do projeto todo — dado errado sem aviso é pior que nenhum dado, mas não bloqueia o caminho feliz (P1/P2) de funcionar primeiro.

**Independent Test**: Pode ser testado fornecendo um arquivo propositalmente corrompido/incompleto e um arquivo válido cujo saldo declarado não bate com a soma das transações reconhecidas, verificando que ambos os casos geram um aviso explícito em vez de falha silenciosa.

**Acceptance Scenarios**:

1. **Given** um arquivo cujo layout não corresponde a nenhum banco suportado, **When** o sistema tenta processá-lo, **Then** o usuário recebe um erro explícito indicando que o banco não foi reconhecido, sem gerar transações parciais.
2. **Given** um arquivo válido de um banco suportado, **When** a soma das transações reconhecidas não reconcilia com a coluna de saldo do arquivo, **Then** o sistema sinaliza a inconsistência para o usuário em vez de prosseguir silenciosamente.

### Edge Cases

- Linhas de metadado no início do arquivo (cabeçalho de agência/conta no Bradesco; título/conta/período/saldo no Inter) não devem virar transações.
- Header de coluna repetido no meio do arquivo (bloco "Últimos Lancamentos" do Bradesco) não deve virar transação nem quebrar o parsing das linhas seguintes.
- Linha de rodapé "Total" (Bradesco) não deve virar transação.
- Linhas em branco em qualquer posição do arquivo devem ser ignoradas sem interromper o processamento.
- `Descrição` vazia no Inter deve usar `Histórico` como fallback, nunca resultar em transação sem descrição.
- `Histórico` do Bradesco nunca inclui nome do favorecido/pagador — isso é uma limitação de dado de origem, não um erro de parsing, e deve ser aceito como tal (não é responsabilidade desta feature enriquecer a descrição).
- Arquivo de um banco não suportado (nem Bradesco, nem Inter) deve ser rejeitado explicitamente.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema MUST detectar automaticamente qual banco (Bradesco ou Inter) gerou um arquivo de extrato, sem exigir seleção manual do usuário.
- **FR-002**: O sistema MUST extrair corretamente as transações de exports do Bradesco, incluindo o caso de duas colunas de valor separadas (crédito/débito), a seção duplicada "Últimos Lancamentos" e o rodapé "Total".
- **FR-003**: O sistema MUST extrair corretamente as transações de exports do Inter, incluindo o caso de coluna de valor única com sinal e o fallback de descrição (`Descrição` vazia → usar `Histórico`).
- **FR-004**: O sistema MUST normalizar valores no formato numérico brasileiro e datas no formato `DD/MM/AAAA` para um formato canônico único, independente do banco de origem.
- **FR-005**: O sistema MUST identificar como transação apenas as linhas que representam movimentações reais, ignorando metadado, linhas em branco, headers repetidos e linhas de totalização, independentemente da posição dessas linhas no arquivo.
- **FR-006**: O sistema MUST calcular um hash de deduplicação por transação (data + descrição + valor + conta) e não criar uma nova transação quando esse hash já existir.
- **FR-007**: O sistema MUST classificar cada transação normalizada como `income` (entrada) ou `expense` (saída) com base no sinal/coluna de origem. A classificação como `transfer` (transferência entre contas próprias) está fora do escopo desta feature.
- **FR-008**: O sistema MUST usar a coluna de saldo corrente do extrato (quando presente) como checagem de sanidade, comparando o saldo declarado com a soma acumulada das transações reconhecidas.
- **FR-009**: O sistema MUST reportar de forma explícita quando um arquivo não puder ser identificado como um banco suportado, ou quando a checagem de saldo (FR-008) indicar inconsistência — nunca falhar silenciosamente nem gerar transações parciais sem aviso.
- **FR-010**: O sistema MUST deixar as transações normalizadas prontas para consumo pela etapa de categorização, sem preencher categoria, subcategoria ou confiança (responsabilidade de uma feature posterior).

### Key Entities *(include if feature involves data)*

- **Transação normalizada**: representa um único lançamento identificado em um extrato. Atributos relevantes a esta feature: hash de deduplicação, data, descrição (como veio do banco), conta/banco de origem, tipo (`income`/`expense`), valor (sempre positivo), mês de referência. Categoria, subcategoria, confiança e identificação de parcelamento são preenchidos por features posteriores e ficam fora do escopo aqui.
- **Arquivo de extrato**: o CSV exportado manualmente pelo usuário a partir do internet banking de um dos dois bancos suportados. Cada arquivo cobre um período (tipicamente um mês) e uma conta.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Um usuário consegue importar o extrato mensal completo de qualquer um dos dois bancos suportados sem precisar editar ou limpar o arquivo manualmente antes.
- **SC-002**: 100% das linhas de transação real presentes em um extrato de exemplo são reconhecidas e convertidas — nenhuma transação real é perdida e nenhuma linha de metadado/header/rodapé vira transação falsa.
- **SC-003**: Reimportar o mesmo arquivo, ou um arquivo com período sobreposto ao já importado, resulta em zero transações duplicadas.
- **SC-004**: A soma das transações importadas de um mês reconcilia com o saldo declarado no extrato de origem, dentro de uma diferença de arredondamento desprezível.
- **SC-005**: Um arquivo de um banco não suportado, ou com saldo que não reconcilia, é sinalizado ao usuário em 100% dos casos, nunca processado como se estivesse correto.

## Assumptions

- Apenas Bradesco e Inter são suportados nesta feature; suporte a outros bancos fica para uma iteração futura.
- Os arquivos de extrato são fornecidos manualmente pelo usuário (exportados pelo internet banking); integração automática com o banco está fora de escopo do projeto como um todo.
- O formato dos arquivos segue o observado nos exports reais coletados entre 24/07 e 22/08/2026; mudanças de layout futuras por parte dos bancos podem exigir ajuste no adapter correspondente.
- Atribuição de categoria, subcategoria e confiança não faz parte desta feature — é responsabilidade da etapa de categorização, que consome a saída desta feature.
- A identificação/confirmação de transferências entre contas próprias não faz parte desta feature — é responsabilidade da categorização combinada com revisão humana.
- Cada arquivo importado corresponde a uma única conta/banco; arquivos misturando contas de bancos diferentes não são um caso suportado.
