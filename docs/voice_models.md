# Conversação por voz e modelos por funcionalidade no FA_Agent

Ambas as funcionalidades pertencem **exclusivamente ao FA_Agent**. Não comunicam com SysTrd, não precisam de PostgreSQL e não executam operações financeiras.

## Conversa por voz

1. Atualizar o repositório e iniciar `START_FA.bat`.
2. Abrir `http://127.0.0.1:8300` em Chrome ou Edge, com a chave OpenAI disponível no processo (`OPENAI_API_KEY` ou `OPENAI_API_KEY_Demo`).
3. Com **Conversação por turnos** desligada, carregar em **Voice**, falar e terminar. A transcrição fica no campo de texto para **revisão antes de Run analysis**. A opção **Respostas faladas** lê a resposta em voz alta depois de submetida.
4. Para uma conversa sem cliques entre turnos, ativar explicitamente **Conversação por turnos** e clicar em **Voice**. O browser deteta pausas depois de falar (heurística), consulta os agentes, reproduz a resposta e volta a ouvir. **Parar voz** termina a sessão e liberta o microfone.
5. O limite de gravação contínua é 45 segundos por turno. Ausência de voz durante 12 segundos termina a sessão automática. A voz não começa sozinha quando se abre a aplicação.

A conversação é **por turnos**, não *full-duplex* ou streaming Realtime. Não utiliza síntese de áudio para produzir conteúdo novo sem a resposta textual dos agentes. A deteção local de pausas é heurística e pode variar com o ruído ambiente.

O áudio gravado é enviado à API OpenAI exclusivamente mediante ação do utilizador. O FA_Agent não grava ficheiros de áudio. As perguntas e respostas textuais ficam guardadas apenas na sessão do browser já usada pelo chat. Os modelos de voz geram custos de API.

## Separador Models & Agents

Na zona superior direita da aplicação, escolher **Models & Agents**. É possível configurar:

| Função | Utilização efetiva |
|---|---|
| Síntese geral | Modelo de IA que produz a interpretação global quando `AI commentary` está ativo |
| Transcrição de voz | Modelo STT da OpenAI |
| Resposta falada | Modelo TTS da OpenAI |
| Voz e idioma | Voz TTS e idioma STT (automático por defeito) |
| Cada agente | Modelo para interpretação opcional baseada nas fontes e cálculos desse agente |

Nos agentes, selecionar um modelo por especialista e marcar **Comentário IA** quando pretender a interpretação adicional. Esta interpretação só é executada com `AI commentary` ativo, em modo Live, até **4 agentes por pergunta**. A síntese global mantém um modelo configurável independente. Pode deixar o modelo do agente vazio para herdar o da síntese.

**Importante:** os agentes `fundamental`, `technical`, `cot` etc. mantêm a extração e os cálculos determinísticos. O modelo associado ao agente **não substitui os cálculos**; só produz comentários adicionais sobre os resultados recolhidos. Agentes ainda não implementados não se tornam funcionais por escolher um modelo.

As configurações são guardadas em `~/.fa_agent/model_settings.json` (ou `FA_MODEL_SETTINGS_FILE`). Não guardam chaves nem alteram o GitHub. A lista de modelos é indicativa e o acesso depende da API da conta. Os erros da API não devem ser ocultados por dados inventados. É possível introduzir um ID de modelo personalizado.

## API e testes

- `GET /api/model-settings` devolve escolhas e catálogo.
- `PUT /api/model-settings` guarda as escolhas com validação.
- `POST /api/voice/transcribe` recebe áudio limitado a 10 MB e devolve texto.
- `POST /api/voice/speak` devolve uma resposta MP3 a partir de texto limitado a 2200 caracteres.
- A API conserva a restrição existente a `localhost`.

```powershell
cd "D:\OD\OneDrive\tech\GitHub\rndm123\fa"
git pull origin main
python -m pip install -e ".[dev,web,ai]"
python -m pytest -q tests/test_voice_input.py tests/test_model_settings.py
.\START_FA.bat
```

Os testes de modelos e áudio simulam a API e não substituem a validação manual do microfone, da reprodução de áudio, da faturação e dos modelos efetivamente disponíveis na conta.
