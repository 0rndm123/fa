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
- The results workspace has contextual tabs: Overview, Financials, Technical, Sources, Specialists and JSON.
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
