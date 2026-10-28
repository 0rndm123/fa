# Ligar FA_Agent aos backtests do SysTrd (opcional)

As aplicações continuam independentes. O SysTrd consulta a PostgreSQL com `SYSTRD_APP_PG_DSN` (role read-only) e disponibiliza a API FastAPI; o FA_Agent **não** conhece a PostgreSQL nem precisa de credenciais da base de dados.

## Primeira ligação no mesmo PC

1. Integrar primeiro a branch/PR da API de backtests no SysTrd e atualizar o clone. Confirmar que o serviço local SysTrd já funciona na porta **8010**. Se necessário, na raiz do SysTrd, com `env_systrd` ativado:

   ```powershell
   python scripts/runControlCenterApi.py
   ```

   Não criar uma segunda instância se o Control Center já estiver aberto. Esta API exige a configuração PostgreSQL que o SysTrd já utiliza para arrancar.

2. Testar no PowerShell (sem credenciais de escrita e sem alterar tabelas):

   ```powershell
   Invoke-RestMethod "http://127.0.0.1:8010/api/v1/backtests/scopes?symbol=BTCUSDT&timespan=D"
   ```

   Verificar `exchange_id`, `timespan` e `calculator_version` devolvidos. Se `items=[]`, não há operações nesta combinação ou ainda não foram gravadas.

3. Atualizar também o clone do FA_Agent com a branch/PR do conector. Na mesma sessão PowerShell em que o FA_Agent vai arrancar:

   ```powershell
   $env:FA_SYSTRD_API_URL = "http://127.0.0.1:8010"
   $env:FA_SYSTRD_CALCULATOR_VERSION = "rm-pilot-experimental-v1"
   .\START_FA.bat
   ```

4. No workbench em `http://127.0.0.1:8300`, selecionar **Live** e perguntar, por exemplo, "Quais os backtests de BTCUSDT em D?" ou selecionar manualmente o agente `backtest`.

   Caso haja mais do que um `exchange_id` ou timeframe, o agente **não** mistura operações. O campo "Exchange" da interface aceita provisoriamente o `exchange_id` numérico do SysTrd. Se tiveres diferentes versões de cálculo, `FA_SYSTRD_CALCULATOR_VERSION` limita o universo explicitamente.

## API consumida pelo agente

- `GET /api/v1/backtests/scopes` descobre as chaves reais.
- `GET /api/v1/backtests/summary` calcula contagens e métricas brutas por chave e versão.
- `GET /api/v1/backtests/operations` devolve até 100 operações fechadas ao agente; registos com PnL e data de saída são apresentados como observações, até haver visualizações específicas.

Não são executados backtests, alterações SQL, recálculos nem operações de escrita pela API.

## Utilização isolada ou remota

- **FA_Agent sozinho:** funciona sem `FA_SYSTRD_API_URL`. O agente de backtests indica que a ligação não está configurada.
- **SysTrd sozinho:** não depende do FA_Agent.
- **Integrados localmente:** HTTP loopback, sem tráfego pesado do motor de cálculo.
- **Máquinas diferentes:** usar o SysTrd já publicado com HTTPS, autorização Supabase e token de acesso de utilizador autorizado `FA_SYSTRD_ACCESS_TOKEN`. Não colocar um token de longa duração em ficheiros versionados e não expor a API local diretamente à Internet.

## Limitações e validação

O conector não considera os resultados validados: as operações `rm-pilot-experimental-v1` incluem estratégias ou stops aproximados e podem divergir do R legacy. As métricas são brutas, sem custos e, em futuros, sem multiplicadores. O chamado `gross_return_ratio` é um rácio de somas de retornos percentuais, **não** um Profit Factor monetário/capital-weighted.

Os testes automatizados são executáveis sem PostgreSQL:

```powershell
python -m pytest -q tests/test_systrd_backtests.py
```

A conexão real só é verificada quando os dois serviços estão a correr na máquina com acesso à PostgreSQL. GitHub por si só não dá acesso ao teu PC.
