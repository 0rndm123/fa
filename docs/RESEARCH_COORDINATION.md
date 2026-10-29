# FA_Agent Research Coordinator e Critical Reviewer — primeira versão

O FA_Agent mantém-se inteiramente independente do SysTrd. Não existem queries SQL, transações, execução de ordens ou partilha de dados com outras aplicações.

## Fluxo LangGraph

    Plan -> Parallel Specialists -> Assess Gaps -> (0 a 2 follow-ups) 
         -> Validate -> Existing Risk Review -> Critical Reviewer -> Synthesize

### Research Coordinator

- Modo predefinido **adaptive**: regras determinísticas detetam quando uma análise de ações necessita de uma segunda consulta a um especialista *já implementado*, sem repetir especialistas nem ultrapassar duas consultas extra.
- **standard**: só executa a seleção inicial, sem delegação.
- **assisted**: um LLM opcional propõe especialistas apenas da lista permitida. Não tem acesso a SQL, APIs arbitrárias, execução de código ou ferramentas de trading. A resposta é validada; se falhar, aplica-se fallback determinístico.
- Respeita seleção explícita dos especialistas, exclusões, classe de ativo e modo Demo. Não executa uma segunda ronda para pedidos com seleção manual, no modo Demo ou para classes de ativos ainda sem follow-ups adequados.
- Não retry automático de fontes falhadas nem ciclos abertos. Um pedido tem no máximo **uma ronda complementar**, limitada a **dois** especialistas. A reutilização/caching entre especialistas continua por evoluir.
- Os planos, agentes realmente consultados e notas de decisão ficam no campo estruturado **research_plan** do relatório.

### Critical Reviewer

- Regista informação em falta, afirmações sem evidência, observações com `source_id` ausente, evidência publicada após `as_of`, limitações de notícias/documentos pesquisados apenas por metadata e incoerências de métricas com o mesmo período declarado.
- Em cada finding indica severidade, categoria, agentes envolvidos e, quando aplicável, `source_id`.
- Pode reduzir o estado do relatório de completed para partial quando identifica problemas graves.
- Não é uma segunda fonte nem um analista de bear case independente; não deve afirmar conclusões de mercado que não existam nos dados.

### Entrada CLI

    fa-agent run --symbol NVDA --asset-class equity --question "Assess governance and company risks" --coordination adaptive
    fa-agent run --symbol NVDA --asset-class equity --coordination standard

Os endpoints de análise aceitam também `coordination: "standard" | "adaptive" | "assisted"` (predefinido adaptive). Na interface, o utilizador não precisa de configurar nada. O separador Overview mostra um resumo de follow-ups efetuados e avisos relevantes do Critical Reviewer, sem adicionar ecrãs.

### Limites e segurança

- A revisão não substitui análise financeira, auditoria nem recomendação de investimento.
- Todos os cálculos e valores continuam a pertencer aos especialistas determinísticos.
- Os dados extraídos de fontes não são tratados como instruções. No modo assisted, apenas o conjunto limitado de estados e a pergunta entram no pedido ao LLM; este não tem ações diretas.
- Modo assisted pode originar custos da API OpenAI. Modos adaptive e standard não necessitam de LLM para a orquestração.
- Os testes não usam chamadas de rede reais ou chaves de API.

## Interface de voz

Na barra de mensagens há dois botões compactos, inspirados na interação familiar de chats de voz, sem reproduzir marcas ou uma interface alheia:

- **Microfone**: ditado, transcrição e revisão antes de enviar.
- **Barras verticais azuis**: conversa por voz baseada em turnos, com respostas faladas e opção de continuar depois de cada resposta; não é áudio full-duplex GPT-Live.
- O estado é visível no próprio botão; os controlos da conversa só aparecem quando a sessão está ativa. Não há um painel de voz adicional.

Testes:

    python -m pytest -q tests/test_research_coordination.py tests/test_compact_voice_ui.py
    python -m pytest -q

## Research Brief – evidência e próximos passos

Depois da validação crítica, o sistema produz automaticamente `research_brief`, sem invocar novos fornecedores nem acrescentar custos de LLM:

- **Objetivo reconhecido**: decisão de investimento, análise financeira, técnica, posicionamento ou investigação geral.
- **Observações fundamentadas**: cada registo numérico é incluído apenas quando o seu `source_id` coincide exatamente com uma evidência do próprio especialista. Não se atribuem métricas sem ligação explícita à fonte.
- **Data de referência**: com `as_of`, são excluídos do resumo registos divulgados ou observados depois dessa data, bem como observações com períodos posteriores. O Critical Reviewer continua a assinalar esses casos.
- **Verificações seguintes**: identificam, por ordem de prioridade, valorização, risco/retorno, demonstrações financeiras, dívida, histórico de preços, qualidade das fontes e limitações de notícias e documentos. Quedas de receita ou FCF negativo só produzem perguntas para investigação, nunca previsões ou ordens.
- **Modo Demo**: contém aviso explícito de dados sintéticos. A ausência de fontes válidas resulta em `insufficient_evidence`; a sua presença só permite `descriptive_only`, nunca uma classificação de compra/venda.

O separador existente **Overview** mostra um quadro curto com os valores datados e a respetiva identificação da fonte, seguido das principais verificações pendentes. O modo `AI commentary` recebe também estas lacunas para contrariar conclusões não suportadas. Os especialistas existentes, o launcher Cloudflare e a interface de voz não foram alterados.

Testar com `python -m pytest -q tests/test_research_brief.py`. A análise de fontes reais e a validação do browser continuam a exigir testes na máquina do utilizador.
