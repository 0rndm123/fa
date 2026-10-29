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
