# TAREFA CODEX: Corrigir e expandir o SFSC, Steel Fan Support Calc

Você está trabalhando em uma aplicação interna chamada SFSC, Steel Fan Support Calc, usada para cálculo preliminar de suportes metálicos para ventiladores industriais.

Contexto técnico:
A aplicação já gera relatório PDF, calcula perfil metálico, base plate, ancoragens e ligações, mas apresentou divergências importantes quando comparada com um modelo global no Autodesk Robot Structural Analysis.

O objetivo desta tarefa é corrigir falhas conceituais, melhorar a clareza do modelo estrutural selecionado pelo usuário e permitir que o usuário escolha quais módulos de cálculo deseja incluir.

A aplicação deve continuar deixando claro que os resultados são preliminares e não substituem verificação por engenheiro estrutural qualificado.

## 1. Problemas identificados

### 1.1 Comparação incorreta entre resultados globais e parciais

Hoje o relatório mistura:
- verificação do perfil metálico;
- verificação da mesa / base plate;
- verificação de ancoragens;
- verificação de ligações;
- diagnóstico global.

Isso gera confusão porque o relatório pode dizer que o perfil IPE80 está OK, mas o diagnóstico global aparece quase no limite devido à base plate.

Corrigir para que o relatório e a UI mostrem claramente:

- Utilização do perfil metálico;
- Utilização da base plate;
- Utilização das ancoragens;
- Utilização das ligações metálicas;
- Utilização governante global;
- Elemento governante;
- Estado individual de cada módulo.

Exemplo esperado:

```text
Perfis metálicos: OK, η = 0.534
Base plate: MARGINAL, η = 0.933
Ancoragens: OK, η = 0.583
Ligações metálicas: OK, η = 0.035
Diagnóstico global: PASSA, MAS ESTÁ NO LIMITE
Verificação governante: Base plate

O relatório atual mostra que a verificação governante é Mesa / base plate, com utilização de 93.3%, enquanto o perfil metálico tem ratio máximo de 0.534 governado por bending_biaxial. Isso precisa estar separado e muito claro.

1.2 Contradição na verificação da base plate

O relatório atual apresenta uma inconsistência:

Flexão da chapa: η = 0.933
Mas também emite aviso dizendo que a espessura fornecida 5 mm é inferior à mínima calculada 10 mm e que a flexão da chapa não verifica.

Isso é contraditório.

Corrigir a lógica:

Se eta <= 1.00 e t_user >= t_min_required: PASSA
Se eta <= 1.00 mas t_user < t_min_required: NÃO PASSA ou MARGINAL_INVALID, conforme regra definida
Se eta > 1.00: NÃO PASSA

A aplicação não pode mostrar simultaneamente “passa” e “não verifica” para a mesma verificação sem explicar o motivo técnico.

Implementar um status granular:

type CheckStatus =
  | "ok"
  | "marginal"
  | "fail"
  | "not_checked"
  | "informative";

E uma estrutura:

type CheckResult = {
  id: string;
  labelKey: string;
  eta?: number;
  status: CheckStatus;
  governing: boolean;
  clauseRefs: string[];
  messages: DiagnosticMessage[];
  inputs: Record<string, unknown>;
  intermediateValues: Record<string, unknown>;
};
1.3 Módulos de cálculo opcionais

O usuário deve poder escolher quais módulos entram no cálculo.

Implementar toggles explícitos na UI e no motor de cálculo:

calculationOptions: {
  includeDynamicFactor: boolean;
  includeBiaxialBending: boolean;
  includeLateralTorsionalBuckling: boolean;
  includeBasePlate: boolean;
  includeAnchors: boolean;
  includeSteelConnections: boolean;
  includeSeismicEquivalentStatic: boolean;
  includeServiceability: boolean;
}

Cada toggle deve:

aparecer na UI;
ser salvo no estado do cálculo;
aparecer no relatório PDF;
aparecer no hash de rastreabilidade;
afetar realmente o cálculo;
ter tradução em PT, EN e ES;
gerar aviso quando desativado.

Exemplo:

Módulo desativado: Encurvadura lateral não incluída. Resultado não deve ser usado como verificação final.
1.4 Suporte selecionado não está claro

Atualmente existem tipos:

Hanger: pendurado em viga com varões roscados
Cantilever 1: consola simples, mão-francesa, pura ou com diagonal
Cantilever 2: consolas simétricas dos dois lados
Cantilever 3: U invertido, pórtico simples
Pedestal: mesa com 2 patins longitudinais
Combined: mesa + pendurais anti-vibração

O problema é que a estrutura real usada nos testes e prints do Robot é mais parecida com uma plataforma metálica em quadro, com tramex, vigas superiores, travessas e escoras/diagonais inclinadas ligadas a apoios em estrutura existente.

Criar um tipo novo e mais claro:

supportType: "platform_frame_braced"

Labels:
PT: Plataforma metálica com quadro e escoras
EN: Braced platform frame
ES: Plataforma metálica con marco y diagonales

Descrição PT:
"Suporte formado por quadro metálico superior com tramex ou grelha metálica, vigas/travessas e escoras ou diagonais inferiores, apoiado ou fixado em estrutura existente."

Esse tipo deve ser o recomendado para casos semelhantes ao modelo do Robot.

Também separar conceitos que hoje estão misturados:

supportType
fanMountingType
walkingSurfaceType
supportFixationMedium
basePlateMode
anchorType
antiVibrationType

Exemplo de modelo:

type SupportType =
  | "hanger_threaded_rods"
  | "cantilever_bracket"
  | "double_cantilever"
  | "inverted_u_frame"
  | "pedestal_skid_frame"
  | "combined_table_hanger"
  | "platform_frame_braced";

type FanMountingType =
  | "direct_flange"
  | "frame_platform"
  | "both"
  | "not_applicable";

type WalkingSurfaceType =
  | "none"
  | "steel_grating_tramex"
  | "checker_plate"
  | "solid_plate"
  | "other";

type SupportFixationMedium =
  | "concrete"
  | "steel_structure"
  | "masonry"
  | "mixed"
  | "unknown";

type BasePlateMode =
  | "none"
  | "fan_to_plate"
  | "support_to_concrete"
  | "support_to_steel"
  | "interface_plate"
  | "equipment_spreader_plate";

Importante:
Tramex não é base plate.
Tramex deve ser tratado como superfície de piso/grelha metálica que distribui carga para vigas/travessas.
Base plate é chapa de ligação ou assento usada para transferência de esforços entre equipamento, suporte, betão ou estrutura metálica.

1.5 Fixação em estrutura metálica

Hoje a aplicação parece calcular engaste/ancoragem apenas em betão, com campos de betão C25/30 e ancoragem embebida.

Implementar novamente o cálculo para fixação em estrutura metálica.

Quando o usuário selecionar:

supportFixationMedium = "steel_structure"

A aplicação deve trocar a lógica de ancoragens em betão para ligações aço-aço.

Campos esperados:

tipo de ligação: soldada, aparafusada, mista;
perfil de suporte existente, se informado;
chapa de ligação;
parafusos;
classe dos parafusos;
furação;
espaçamentos;
bordos;
soldas;
stiffeners, quando aplicável;
verificação local simplificada do elemento receptor, quando possível;
aviso quando o elemento receptor não for verificado.

Criar estruturas:

type SteelFixationInput = {
  connectionType: "bolted" | "welded" | "bolted_welded";
  receivingMemberSectionId?: string;
  receivingMemberMaterial?: string;
  plateThicknessMm?: number;
  boltDiameterMm?: number;
  boltClass?: "4.6" | "5.6" | "8.8" | "10.9";
  numberOfBolts?: number;
  holeDiameterMm?: number;
  edgeDistanceMm?: number;
  spacingMm?: number;
  weldSizeMm?: number;
  weldLengthMm?: number;
  hasStiffeners?: boolean;
};

Cálculos mínimos:

corte nos parafusos;
tração nos parafusos;
interação tração+corte;
esmagamento/furação na chapa, simplificado;
solda por tensão nominal;
chapa de ligação à flexão/corte;
aviso explícito se o perfil receptor não for verificado.

Não remover o cálculo em betão. Deve existir alternância:

concrete: EN 1992-4
steel_structure: EN 1993-1-8
1.6 Idiomas PT, EN e ES em tudo

O sistema deve ter alternância completa de idioma:

Português;
Inglês;
Espanhol.

Tudo deve usar chaves i18n:

UI;
selects;
labels;
tooltips;
mensagens de erro;
warnings;
relatório PDF;
nomes de módulos;
tipos de suporte;
notas técnicas;
diagnósticos;
unidades;
cabeçalhos de tabelas;
disclaimers.

Não deixar texto hardcoded.

Criar ou revisar:

locales/pt.json
locales/en.json
locales/es.json

Exemplo:

{
  "support.types.platform_frame_braced.label": "Plataforma metálica com quadro e escoras",
  "support.types.platform_frame_braced.description": "Suporte formado por quadro metálico superior com tramex ou grelha metálica, vigas/travessas e escoras ou diagonais inferiores, apoiado ou fixado em estrutura existente.",
  "calculation.modules.dynamicFactor": "Fator dinâmico",
  "calculation.modules.biaxialBending": "Flexão biaxial",
  "calculation.modules.lateralTorsionalBuckling": "Encurvadura lateral",
  "calculation.modules.basePlate": "Mesa / base plate",
  "calculation.modules.anchors": "Ancoragens em betão",
  "calculation.modules.steelConnections": "Ligações metálicas",
  "surface.tramex.label": "Tramex / grelha metálica"
}
2. Novo fluxo de UI esperado
2.1 Passo 1: tipo de suporte

Mostrar cartões com imagem ou descrição curta:

Pendurado em viga, varões roscados
Consola simples com ou sem diagonal
Consolas simétricas dos dois lados
Pórtico U invertido
Mesa com patins longitudinais
Mesa + pendurais anti-vibração
Plataforma metálica com quadro e escoras, recomendado para estruturas tipo Robot

Cada tipo deve ter:

label;
descrição;
quando usar;
limitações;
ícone ou placeholder.
2.2 Passo 2: superfície de apoio

Adicionar campo:

walkingSurfaceType

Opções:

Nenhuma;
Tramex / grelha metálica;
Chapa xadrez;
Chapa lisa;
Outro.

Para tramex:

não calcular como chapa rígida;
tratar como carga permanente distribuída;
permitir informar peso próprio em kN/m² ou kg/m²;
permitir informar se a carga do equipamento está distribuída na superfície ou aplicada em pontos.
2.3 Passo 3: fixação do suporte

Campo:

supportFixationMedium

Opções:

Betão;
Estrutura metálica;
Misto;
Desconhecido.

Se betão:

mostrar classe do betão;
ancoragens;
profundidade;
cone de betão;
pull-out;
pry-out.

Se estrutura metálica:

ocultar classe do betão;
mostrar ligação aço-aço;
parafusos;
soldas;
chapa;
perfil receptor;
stiffeners.
2.4 Passo 4: módulos de cálculo

Mostrar checkboxes:

Incluir fator dinâmico;
Incluir flexão biaxial;
Incluir encurvadura lateral;
Incluir base plate;
Incluir ancoragens em betão;
Incluir ligações metálicas;
Incluir sísmica simplificada;
Incluir ELS/deformações.

Regras:

Se supportFixationMedium = concrete, anchors pode ser ativado.
Se supportFixationMedium = steel_structure, anchors em betão deve ser desativado ou oculto.
Se supportFixationMedium = steel_structure, steelConnections deve ficar disponível.
Se includeBasePlate = false, não calcular nem deixar governar base plate.
Se includeBasePlate = true, base plate deve aparecer como módulo separado no relatório.
Se módulo for desativado, status = not_checked e mensagem de limitação deve aparecer no relatório.
3. Motor de cálculo

Refatorar para uma arquitetura modular.

Criar funções ou serviços separados:

calculateActions(input, options)
calculateSupportModelForces(input, supportType, options)
checkSteelSection(input, forces, options)
checkDynamicFactor(input, options)
checkBiaxialBending(section, forces, options)
checkLateralTorsionalBuckling(section, forces, options)
checkBasePlate(basePlateInput, forces, options)
checkConcreteAnchors(anchorInput, forces, options)
checkSteelConnections(connectionInput, forces, options)
checkServiceability(modelInput, forces, options)
aggregateResults(checkResults)

Cada função deve retornar CheckResult.

O agregador deve:

ignorar módulos not_checked para governar, mas listar no relatório;
considerar fail como diagnóstico global fail;
considerar marginal se eta >= 0.85 e eta <= 1.00;
considerar ok se eta < 0.85;
calcular governingEta como máximo eta válido;
guardar governingCheckId.

Regra sugerida:

if any status === "fail": globalStatus = "fail"
else if maxEta >= 0.85: globalStatus = "marginal"
else globalStatus = "ok"

Mas permitir configuração dos thresholds.

4. Correção da comparação com Robot

Adicionar modo de cálculo para benchmark:

calculationMode:
  | "engineering_estimate"
  | "robot_benchmark"
  | "full_preliminary_design";
robot_benchmark

Este modo deve permitir comparar com Robot:

sem base plate;
sem ancoragens;
sem ligações;
sem sísmica;
sem fator dinâmico, se o usuário quiser;
carga vertical distribuída equivalente;
mesmo aço;
mesmo perfil;
mesmos apoios ideais;
relatório destacando que é benchmark de barra, não verificação final.

Objetivo:
evitar comparar “Robot barras” contra “SFSC global com base plate e ancoragens”.

5. Relatório PDF

Reorganizar relatório com esta estrutura:

Capa
Resumo executivo
Entradas do usuário
Tipo de suporte selecionado
Superfície de apoio, tramex/chapa/nenhuma
Meio de fixação, betão ou estrutura metálica
Módulos incluídos e excluídos
Ações e combinações
Esforços no modelo simplificado
Verificação do perfil metálico
Verificação de estabilidade e encurvadura
Base plate, se incluída
Ancoragens em betão, se incluídas
Ligações metálicas, se incluídas
ELS/deformações, se incluído
Verificação final por módulo
Avisos e limitações
Rastreabilidade e hashes
Assinaturas

A seção de resumo deve mostrar uma tabela assim:

Módulo                         Estado       η       Governante
Perfil metálico                OK           0.534   Não
Base plate                     MARGINAL     0.933   Sim
Ancoragens em betão            OK           0.583   Não
Ligações metálicas             OK           0.035   Não
Encurvadura lateral            OK           0.221   Não
Sísmica simplificada           Incluída     N/A     Não

Se algum módulo estiver desativado:

Ancoragens em betão            Não verificado
Motivo: módulo desativado pelo usuário ou meio de fixação = estrutura metálica.
6. Dados e catálogos de perfis

Manter catálogos:

IPE;
HEA;
HEB;
RHS;
SHS;
UPN.

Adicionar seletor de seção mais claro:

família;
perfil;
material;
orientação do perfil;
eixo forte/eixo fraco;
rotação da seção.

Para IPE e UPN, a orientação deve ser explícita porque a diferença entre eixo forte e eixo fraco altera muito o resultado.

Adicionar campos:

sectionOrientation: "strong_axis_vertical" | "weak_axis_vertical" | "custom_rotation";
rotationDeg?: number;
7. Correções específicas de base plate

Renomear UI para evitar confusão:

“Mesa / base plate” pode continuar, mas deve ter tooltip:
PT: “Chapa de interface ou assento entre equipamento, suporte e estrutura. Não é o tramex.”
EN: “Interface or bearing plate between equipment, support and structure. It is not the grating.”
ES: “Placa de interfaz o asiento entre equipo, soporte y estructura. No es la rejilla.”

Adicionar:

basePlateRole:
  | "equipment_spreader"
  | "support_foot_plate"
  | "connection_plate_to_steel"
  | "connection_plate_to_concrete"
  | "none";

Se walkingSurfaceType = tramex, não ativar base plate automaticamente.

8. Testes obrigatórios

Criar testes unitários para:

8.1 Diagnóstico global
perfil OK e base plate marginal resulta global marginal;
perfil OK e base plate disabled não pode governar;
módulo disabled aparece como not_checked;
fail em qualquer módulo resulta global fail.
8.2 Base plate contraditória
eta <= 1 e t_user < t_min deve gerar status coerente, sem mensagem contraditória;
eta > 1 deve falhar;
t_user >= t_min e eta <= 1 deve passar.
8.3 Fixação em betão vs estrutura metálica
se fixationMedium = concrete, mostrar anchors e concreteClass;
se fixationMedium = steel_structure, ocultar concreteClass e anchors em betão;
se fixationMedium = steel_structure, mostrar steelConnectionInput;
não calcular cone de betão quando fixação é estrutura metálica.
8.4 i18n
não pode haver labels hardcoded na UI principal;
todos os supportTypes devem ter tradução PT, EN e ES;
todos os calculationModules devem ter tradução PT, EN e ES;
relatório PDF deve respeitar idioma selecionado.
8.5 Benchmark Robot
modo robot_benchmark exclui base plate, ancoragens e ligações;
modo full_preliminary_design inclui módulos conforme seleção do usuário;
comparação de ratio de bending_y isolado deve ser separada do diagnóstico global.

9. Critérios de aceite

A tarefa só está concluída quando:

O usuário consegue selecionar claramente o tipo de suporte “Plataforma metálica com quadro e escoras”.
O usuário consegue selecionar se há tramex sem confundir com base plate.
O usuário consegue escolher se a fixação é em betão ou estrutura metálica.
A aplicação calcula ligação em estrutura metálica quando selecionado.
O usuário consegue ativar/desativar fator dinâmico, flexão biaxial, encurvadura lateral, base plate, ancoragens, ligações e sísmica.
O relatório mostra módulos incluídos e excluídos.
O relatório não mistura utilização do perfil com utilização da base plate.
Não existe contradição entre eta da base plate e espessura mínima.
O sistema tem PT, EN e ES em UI e PDF.
Existem testes automatizados cobrindo as regras acima.
O build, lint e testes passam.
10. Restrições importantes
Não remover as verificações existentes sem substituir por equivalente melhor.
Não hardcodar texto em português, inglês ou espanhol.
Não tratar tramex como base plate.
Não calcular ancoragem em betão quando a fixação selecionada for estrutura metálica.
Não deixar base plate governar se o módulo estiver desativado.
Não comparar diagnóstico global SFSC com verificação de barras do Robot como se fossem equivalentes.
Preservar rastreabilidade dos inputs, opções ativadas/desativadas e hashes de dados.
Manter o relatório com marcação preliminar e não aprovado para construção.

Corrigir a confusão conceitual entre "base plate" e "superfície superior de distribuição".

Base plate não deve ser usada para representar tramex, grelha metálica ou chapa superior apoiada nas vigas.

Criar dois módulos separados:

1. Surface / Load Distribution Surface
   Representa tramex, grelha metálica, chapa xadrez, chapa lisa ou chapa superior.
   Serve para transformar peso do equipamento em carga de área kN/m² e distribuir para as vigas.
   Não calcula cone de betão, pull-out, pry-out ou ancoragens.

2. Base Plate / Connection Plate
   Representa chapa de base, chapa de ligação ou chapa de fixação entre suporte e betão/estrutura metálica.
   Calcula parafusos, soldas, chumbadores, contato, arrancamento, corte e flexão da chapa.
   Só deve aparecer quando houver ligação real por chapa.

11. Entrega esperada

Ao finalizar, devolver:

Lista de arquivos alterados.
Resumo das mudanças.
Novos tipos/interfaces criados.
Explicação de como o cálculo agora separa módulos.
Como testar manualmente o caso do suporte dos ventiladores.
Resultado dos testes.
Eventuais limitações ainda existentes.

