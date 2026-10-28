# Entrada por voz no FA_Agent

A aplicação suporta ditar perguntas com um botão de microfone no chat, sem ligação ao SysTrd.

## Utilização

1. Arrancar o FA_Agent habitualmente com `START_FA.bat` em `http://127.0.0.1:8300`.
2. O mesmo `OPENAI_API_KEY` ou `OPENAI_API_KEY_Demo` usado pela aplicação permite a transcrição, desde que tenham sido instalados os extras `.[dev,web,ai]`.
3. Clicar **Voice** e permitir o microfone no browser.
4. Falar e clicar **Stop recording** (limite de 90 segundos). A gravação é enviada para `POST /api/transcribe-audio`.
5. A transcrição é adicionada à caixa de pergunta. **Rever ou editar o texto antes de carregar em Run analysis.** A transcrição nunca executa automaticamente uma análise nem qualquer ação de trading.

A interface exige `MediaRecorder` e `getUserMedia` num contexto seguro (localhost é aceite). Edge/Chrome recentes são recomendados para o Windows. A compatibilidade depende do browser e dos formatos suportados; Safari e Firefox podem variar. Se o microfone não for suportado, o utilizador pode utilizar o ditado do teclado do sistema operativo.

## Privacidade, limites e segurança

- A gravação é capturada **apenas mediante clique explícito**. Terminar a gravação envia o áudio para a API do FA_Agent, que o reencaminha à **API OpenAI para transcrição**.
- Não guardamos o áudio no disco, na base de dados nem no histórico da aplicação. O browser mantém temporariamente os chunks em memória até enviar e elimina a referência depois.
- O endpoint é apenas local através do middleware existente (loopback + verificação de origem).
- O limite de upload é **10 MiB**, e o limite de gravação no browser é **90 segundos**. A resposta textual é limitada a 6000 caracteres.
- Os formatos de áudio aceites incluem WebM, MP4/M4A e Ogg; o browser escolhe o formato suportado.
- O endpoint não executa backtests, ordens, análises nem chamadas a agentes. A transcrição é editável pelo utilizador, que decide quando submeter.
- A chave OpenAI permanece **no backend**. Nunca é enviada ao browser.
- A transcrição utiliza `gpt-4o-mini-transcribe` (chamada à API com custo associado); não é a conversa de voz em tempo real da aplicação ChatGPT.

## Configuração opcional

```powershell
# Só para a sessão atual; no arranque da app
$env:FA_VOICE_LANGUAGE = "pt"
```

Sem `FA_VOICE_LANGUAGE`, o fornecedor deteta automaticamente o idioma. Para português usa-se `pt`, para inglês `en`.

## Testes

```powershell
python -m pip install -e ".[dev,web,ai]"
python -m pytest -q tests/test_voice_input.py
```

Os testes não enviam áudio à OpenAI e não precisam de microfone físico. A gravação real deve ser testada manualmente no browser e numa máquina com a chave configurada.
