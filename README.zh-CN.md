# Wox Hermes

[English](README.md) | [中文](README.zh-CN.md)

Wox Hermes 是一个 Wox 插件，用来把 Wox 变成 Hermes Agent 的快速指令入口。

它不会把每一次输入都直接交给完整 agent。插件会根据意图自动路由：

- 本地 macOS 能力，例如 Apple 提醒事项，直接本地读取，降低延迟
- 简单问题走快速问答模式
- 复杂执行任务显式交给 Hermes Agent

## 依赖要求

- Hermes gateway 已运行，并启用 API Server。
- Hermes 健康检查接口可用：`http://127.0.0.1:8642/v1/health`。
- Wox 2.x。
- 使用提醒事项通道时，需要给 Wox 授权访问 macOS Reminders。

## Hermes API 配置

在 `~/.hermes/.env` 中加入：

```env
API_SERVER_ENABLED=true
API_SERVER_KEY=change-me-local-dev
API_SERVER_HOST=127.0.0.1
API_SERVER_PORT=8642
```

重启 Hermes：

```bash
hermes gateway restart
```

检查 API：

```bash
curl http://127.0.0.1:8642/v1/health \
  -H "Authorization: Bearer change-me-local-dev"
```

## 使用方式

在 Wox 中输入：

```text
hermes status
h 看一下 Apple 里的提醒事项我还有什么没做
h q 用一句话解释这个报错
h agent 帮我检查这个项目并给出修改方案
h full 做一个完整分析
```

## 路由规则

默认触发词：

```text
hermes
h
```

当前规则：

- `h status` 检查本地 Hermes API 是否在线。
- 包含 `提醒事项`、`提醒`、`todo`、`remind`、`reminders` 的查询，会走本地 Apple Reminders 通道。
- `h q ...`、`h quick ...`、`h 快问 ...` 强制走快速问答模式。
- `h agent ...` 强制走 Hermes Agent 模式。
- `h full ...` 强制走完整深度模式。
- 其他短自然语言问题默认走快速问答。
- 偏执行的请求，例如文件、项目、修改、运行、搜索类任务，会路由到 Hermes Agent。

## 行为说明

- 在 Wox 输入时不会反复请求 Hermes。
- 选中结果并按 Enter 后才执行。
- 回复会直接显示在 Wox 结果和预览面板里。
- 默认不会覆盖剪贴板。
- 需要时可以使用“复制上一次回复”动作。

## 本地安装

把项目复制到 Wox 用户插件目录：

```bash
mkdir -p ~/.wox/wox-user/plugins/95d041d3-be7e-4b20-8517-88dda2db280b@0.1.0
cp -R ./* ~/.wox/wox-user/plugins/95d041d3-be7e-4b20-8517-88dda2db280b@0.1.0/
```

然后重启 Wox。

## 配置项

插件会读取以下可选环境变量：

```env
HERMES_API_BASE_URL=http://127.0.0.1:8642
HERMES_API_KEY=change-me-local-dev
```

## 项目状态

这是一个早期个人项目。当前重点是让 Wox 更像一个实用的指令路由器，而不是一个慢速聊天框。

计划中的改进：

- 更细的提醒事项筛选，例如今天、逾期、指定清单
- Hermes 异步任务、进度展示和取消
- 可配置路由规则
- 更丰富的结果预览和历史记录
- 面向 Wox 用户的打包安装流程
