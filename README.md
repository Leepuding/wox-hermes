# Wox Hermes

Use Wox to send commands to a local Hermes Agent API server.

## Requirements

- Hermes gateway running with API server enabled.
- Hermes health endpoint returning ok at `http://127.0.0.1:8642/v1/health`.
- Wox 2.x.

## Usage

In Wox:

```text
hermes status
hermes 你好，简单介绍一下你能做什么
h 总结当前剪贴板内容
```

The plugin reads optional overrides from:

```env
HERMES_API_BASE_URL=http://127.0.0.1:8642
HERMES_API_KEY=change-me-local-dev
```
