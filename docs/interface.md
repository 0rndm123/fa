# FA Agent Research Workbench (local web app)

## Run from your existing clone (Windows)

~~~powershell
git pull origin main
python -m pip install -e ".[dev,web,ai]"
.\START_FA.bat
~~~

Open http://127.0.0.1:8300 (bound to 127.0.0.1 only). The app is independent of SysTrd and has no public tunnel.

## Interaction

- Natural-language chat with a scrollable history and follow-up prompts.
- Three presentation states: split view, minimized chat rail, maximized chat.
- Desktop drag handle allows resizing the chat/results split.
- The results workspace has contextual tabs: Quote, Overview, Financials, Technical, Debt & Liquidity, Governance, Sector & Peers, Sources, Specialists and JSON, displayed as appropriate.
- Financial Data subagent retrieves up to six fiscal years of available SEC XBRL annual metrics, presented in a line chart and table.
- Technical analysis accepts local price CSV (date,close, max 2 MB) and plots up to 250 closing observations.
- User can select asset, asset class, research horizon, demo/live mode and manual/automatic specialist selection.
- The AI commentary checkbox is optional and uses OPENAI_API_KEY or OPENAI_API_KEY_Demo.
- JSON export downloads the full structured response.
- Messages persist only in the current browser tab via sessionStorage; reports persist only until reload unless exported.
- This is a research prototype. Per-agent streaming, autonomous tool planning and independent critical agents are not yet implemented.

## Live data

SEC financials require SEC_USER_AGENT with an identifying contact email in the process environment.
Live news agent retrieves RSS headlines, not article contents. The UI displays this distinction.
The default demo uses fabricated test data and refuses LLM calls.
Financial and technical data are not guaranteed complete, adjusted or suitable for investment decisions.

## Security / limitations

This development UI is local only. Do not expose port 8300 publicly. No account authentication is implemented.
API requests are checked for loopback access and cross-origin browser mutations are restricted.
CSV uploads are limited to 2 MB and stored temporarily in the current server process.
Source and LLM text is inserted via textContent, not interpreted as HTML.
The web interface does not execute trades or perform unrestricted shell/SQL operations.


## Interactive market charts (v0.5)

- Quotes from Yahoo or Binance may carry genuine hourly OHLC bars.
- Users can switch between Line and Candles when the data supplier actually returns valid OHLC.
- Wheel zoom, pointer drag pan, hover crosshair and time/price inspection; Reset restores the latest range.
- If OHLC is missing, only Line is available. Candles are **never** fabricated from close values.
- The technical specialist can retrieve intraday market observations when no CSV is uploaded, but this does not imply daily/weekly technical indicators.

## Specialist conversation routing

Examples that trigger focused subagent selections:
- "Como evoluíram as receitas e as margens da NVIDIA?" → Financial Performance + Fundamental + Financial Data
- "Qual a dívida e liquidez da NVIDIA?" → Debt & Liquidity + Financial Data
- "Como está a governance da NVIDIA?" → Governance document investigator
- "Analisa o setor e os concorrentes da NVIDIA" → Sector Context + Competition
- "Qual é o RSI da NVIDIA?" → Technical via market observations

Company names in the question override a different selected symbol when an exact known alias is recognized.
Manual agent selection always overrides automatic intent routing.

Only Financial Performance, Financial Data and simple balance ratios have substantive deterministic fact computation.
Governance, Competition and Industry Context are currently documentary *research starters*, not completed independent qualitative assessments.


## Windows SEC_USER_AGENT troubleshooting

The FA_Agent financial subagents use SEC_USER_AGENT to identify automated
reads from the US SEC. Set it with the FA_Agent name and a real contact
email in a Windows User environment variable. The contact is kept local to
the user settings and is not committed to GitHub.

The start batch file will import the Windows User setting into its own
process if it is not already set. The Python provider independently falls
back to the current user's Windows registry environment even when a server
was started before the User variable was registered.

The application exposes only configuration *readiness* and its *source*
on GET /api/capabilities, via sec_configured and sec_config_source
(process, windows_user or missing). It does not expose the contact address.

In PowerShell, use this privacy-safe readiness diagnostic:
    python -c "from fa_agents.providers import sec_user_agent_config; v,s=sec_user_agent_config(); print(bool(v),s)"

An old FA_Agent server already bound to 127.0.0.1:8300 must be stopped
before the updated script starts. If the server is still running, a
browser may show the old code even after a successful git pull.
