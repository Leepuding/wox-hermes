# Wox Hermes

Wox Hermes is a Wox plugin that turns Wox into a fast command entrance for
Hermes Agent.

The plugin does not send every query to a heavy agent by default. It routes
commands by intent:

- local macOS actions, such as Apple Reminders, run directly for low latency
- quick questions go through a concise Hermes request
- complex execution tasks can be sent to Hermes Agent explicitly

## Requirements

- Hermes gateway running with API server enabled.
- Hermes health endpoint returning ok at `http://127.0.0.1:8642/v1/health`.
- Wox 2.x.
- macOS Reminders permission for Wox when using the Reminders route.

## Hermes API setup

Add this to `~/.hermes/.env`:

```env
API_SERVER_ENABLED=true
API_SERVER_KEY=change-me-local-dev
API_SERVER_HOST=127.0.0.1
API_SERVER_PORT=8642
```

Restart Hermes:

```bash
hermes gateway restart
```

Check the API:

```bash
curl http://127.0.0.1:8642/v1/health \
  -H "Authorization: Bearer change-me-local-dev"
```

## Usage

In Wox:

```text
hermes status
h 看一下 Apple 里的提醒事项我还有什么没做
h q 用一句话解释这个报错
h agent 帮我检查这个项目并给出修改方案
h full 做一个完整分析
```

## Routing

The default trigger keywords are:

```text
hermes
h
```

Routing rules:

- `h status` checks the local Hermes API health endpoint.
- Queries mentioning `提醒事项`, `提醒`, `todo`, `remind`, or `reminders`
  use the local Apple Reminders route.
- `h q ...`, `h quick ...`, or `h 快问 ...` forces quick Q&A mode.
- `h agent ...` forces Hermes Agent mode.
- `h full ...` forces full-depth mode.
- Other short natural-language queries default to quick Q&A.
- Execution-oriented queries, such as file/project/modify/run/search tasks,
  are routed to Hermes Agent.

## Behavior

- Typing in Wox does not call Hermes repeatedly.
- Press Enter on the result to execute the routed action.
- Results are displayed in Wox and the preview panel.
- The plugin does not overwrite the clipboard by default.
- A copy action is available for the latest response.

## Install locally

Copy this project into Wox's user plugin folder:

```bash
mkdir -p ~/.wox/wox-user/plugins/95d041d3-be7e-4b20-8517-88dda2db280b@0.1.0
cp -R ./* ~/.wox/wox-user/plugins/95d041d3-be7e-4b20-8517-88dda2db280b@0.1.0/
```

Then restart Wox.

## Configuration

The plugin reads optional overrides from:

```env
HERMES_API_BASE_URL=http://127.0.0.1:8642
HERMES_API_KEY=change-me-local-dev
```

## Project status

This is an early personal project. The current focus is making Wox feel like a
practical command router rather than a slow chat box.

Planned improvements:

- better Reminders filtering, such as today, overdue, and list-specific views
- async Hermes runs with progress and cancellation
- configurable routing rules
- richer result previews and command history
- packaged install workflow for Wox users
