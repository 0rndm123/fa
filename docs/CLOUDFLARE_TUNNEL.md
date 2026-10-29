# FA_Agent – Cloudflare Tunnel independente (Windows)

Este launcher expõe somente o FA_Agent, não o SysTrd, através de um Cloudflare named tunnel exclusivo e de uma aplicação Cloudflare Zero Trust Access com uma política Allow restrita. O backend exige um JWT Cloudflare Access válido em TODAS as rotas.

## Preparar uma vez

1. Instalar cloudflared e criar um named tunnel exclusivo para FA_Agent; por exemplo executar cloudflared tunnel login, cloudflared tunnel create fa-agent e cloudflared tunnel route dns fa-agent fa.exemplo.pt. Em alternativa, criar o túnel no Zero Trust Dashboard.
2. Criar uma aplicação Self-hosted no Zero Trust → Access → Applications para https://fa.exemplo.pt. Configurar política Allow apenas para os e-mails autorizados (sem Bypass público). Copiar o Application Audience (AUD) e o Team domain (exemplo tua-equipa.cloudflareaccess.com).
3. Guardar fora do GitHub o ficheiro %USERPROFILE%\.cloudflared\fa-agent.yml, com um tunnel ID e credentials-file próprios:

    tunnel: UUID-DO-TUNEL
    credentials-file: C:/Users/TEU_UTILIZADOR/.cloudflared/UUID-DO-TUNEL.json
    ingress:
      - hostname: fa.exemplo.pt
        service: http://127.0.0.1:8300
        originRequest:
          httpHostHeader: fa.exemplo.pt
      - service: http_status:404

O ficheiro do túnel, o JSON de credenciais, tokens e certificados NUNCA devem ser guardados no repositório público.

## Configurar variáveis Windows User

No PowerShell, substituir os valores de exemplo:

    [Environment]::SetEnvironmentVariable("FA_CF_ACCESS_TEAM_DOMAIN","tua-equipa.cloudflareaccess.com","User")
    [Environment]::SetEnvironmentVariable("FA_CF_ACCESS_AUD","AUD_DA_APLICACAO_FA_AGENT","User")
    [Environment]::SetEnvironmentVariable("FA_TUNNEL_HOSTNAME","fa.exemplo.pt","User")

Abrir nova consola depois de definir as variáveis. Pode também definir FA_TUNNEL_CONFIG para indicar outro ficheiro YAML.

Instalar as dependências:

    cd "D:\OD\OneDrive\tech\GitHub\rndm123\fa"
    python -m pip install -e ".[dev,web,ai]"

## Arranque e paragem

    .\START_FA_CLOUDFLARE.bat

O launcher faz os pré-testes, abre o servidor protegido numa nova consola em 127.0.0.1:8300 e inicia cloudflared no terminal atual. Abrir https://fa.exemplo.pt e confirmar que a Cloudflare exige autenticação. Ctrl+C termina o túnel; fechar também a consola da API para parar o backend.

Não iniciar duas instâncias na mesma porta. No modo remoto, também os pedidos diretos a localhost exigem JWT Access, para impedir bypass. Para voltar ao modo local, encerrar a instância protegida e iniciar START_FA.bat sem FA_REMOTE_AUTH_MODE.

## Segurança e restrições

- Proibido quick tunnel (cloudflared tunnel --url) sem autenticação. O launcher exige named tunnel configurado e validação no origin.
- Não alterar o servidor para host 0.0.0.0; só loopback.
- Todas as rotas exigem assinatura RS256 válida, emissor correto, audience, expiração e identidade no Cf-Access-Jwt-Assertion.
- Pedidos com Host incorreto e origens externas são rejeitados.
- Não é ainda uma aplicação multiutilizador com quotas, auditoria por utilizador ou isolamento de conversas. Não distribuir a terceiros nesta fase.
- A voz e a análise de IA usam a API OpenAI com eventuais custos.
- SysTrd e FA_Agent permanecem independentes; a integração entre eles está suspensa.

Testes sem acesso real à Cloudflare:

    python -m pytest -q tests/test_cloudflare_access.py

Testar manualmente o login, bloqueio de utilizadores não autorizados, funcionalidades de voz e sessões no domínio publicado antes de confiar no acesso remoto.
