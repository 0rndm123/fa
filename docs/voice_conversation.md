# Conversação por voz no FA_Agent (primeira versão)

O FA_Agent mantém os mesmos agentes e a mesma interface para pesquisas sobre ativos, dados financeiros, indicadores técnicos, COT, derivados cripto e, quando integrada a extensão independente, os backtests do SysTrd.

## Como funciona

1. Abrir a aplicação local em `http://127.0.0.1:8300` e escolher o ativo, mercado e modo **Live**.
2. Clicar em **Falar** e autorizar o microfone. Falar sobre o ativo selecionado.
3. Clicar em **Terminar pergunta**. A gravação é transcrita e o texto é enviado ao mecanismo de análise que já existe. O resultado aparece no chat e nos painéis.
4. A aplicação produz a resposta em áudio. O utilizador pode interromper a reprodução com **Parar áudio** e continuar por texto ou por voz.
5. **Continuar por voz (turnos)** é opcional. Quando ligado, o gravador deteta pausas após a fala, envia cada pergunta e volta a ouvir depois de terminar a resposta. O microfone **não** arranca ao abrir a página. Se não houver fala durante 12 segundos, termina automaticamente; há também um limite de 45 segundos por gravação.

As conversas são preservadas na sessão do navegador e a seleção de símbolo/classe de ativo delimita o histórico enviado para síntese. Quando o usuário altera o ativo, o modo de voz termina; o texto e os relatórios anteriores permanecem visíveis. Em Live, a conversação ativa automaticamente o comentário LLM quando a API key estiver configurada, para tirar partido do histórico de até oito mensagens (sem inventar dados fora dos resultados obtidos pelos agentes).

## Implementação e portabilidade

- `GET /api/capabilities` inclui `voice.available` e `voice.mode=turn_based`.
- `POST /api/voice/transcribe` recebe até 10 MB de áudio WebM, MP4, MP3 ou WAV, utiliza o modelo `gpt-transcribe` e devolve `{"text":"..."}`.
- `POST /api/voice/speak` recebe no máximo 2200 caracteres e devolve áudio MP3, usando `gpt-4o-mini-tts` com a voz `cedar`.
- A página usa `MediaRecorder`/Web Audio para captura e deteção simples de pausas. A reprodução de áudio só ocorre quando a conversa por voz foi iniciada.
- Não são necessários módulos de voz do SysTrd nem credenciais PostgreSQL. O FA_Agent pode funcionar isoladamente; quando existir acesso aos resultados dos backtests, utiliza a respetiva API.
- As credenciais ficam **apenas no servidor local**, através de `OPENAI_API_KEY` ou `OPENAI_API_KEY_Demo`, nunca no JavaScript.
- O servidor não guarda ficheiros de áudio. Continua limitado a loopback e a requests da mesma origem. O browser precisa de permissão de microfone.

## Limitações desta versão

- A conversação é **por turnos**, não é *full duplex* em tempo real. Não se pode falar simultaneamente com o agente e receber áudio contínuo palavra a palavra. Está previsto avaliar WebRTC/Realtime API em fase posterior.
- A deteção de silêncio é heurística. Ruído ambiente pode afetar os limites e terminar uma pergunta prematuramente. Pode sempre optar pelo botão manual.
- A reprodução falada é uma versão limitada às primeiras 1800 letras da resposta; a resposta completa e os gráficos continuam visíveis. Se a resposta for extensa, pode pedir um resumo oral mais curto.
- A continuidade temática depende dos agentes e dos dados disponíveis. Uma conversa fluida não torna os dados incompletos mais fiáveis nem valida automaticamente estratégias experimentais.
- Há utilização faturável das APIs OpenAI para transcrição e voz, além do comentário LLM quando utilizado.
- O suporte de `MediaRecorder`, áudio e permissões pode variar com o navegador.

## Testar localmente, depois de integrar o PR

```powershell
cd "D:\OD\OneDrive\tech\GitHub\rndm123\fa"
git pull origin main
python -m pip install -e ".[dev,web,ai]"
python -m pytest -q tests/test_voice.py
.\START_FA.bat
```

Escolher **Live**, introduzir por exemplo `NVDA`, clicar **Falar** e dizer «Como evoluíram as margens da NVIDIA?». Esperar pela transcrição, resposta textual e resposta sonora. Repetir com uma pergunta de seguimento sobre o mesmo ativo.

A utilização real do microfone, a faturação/autorização da API e a qualidade das transcrições requerem teste no computador do utilizador. Os testes automatizados substituem a API por respostas simuladas, pelo que não fazem chamadas de áudio pagas.

Documentação técnica usada: https://developers.openai.com/api/docs/guides/speech-to-text e https://developers.openai.com/api/docs/guides/text-to-speech.
