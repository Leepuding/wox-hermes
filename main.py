from __future__ import annotations

import asyncio
import json
import os
import subprocess
import urllib.error
import urllib.request
from typing import Any

from wox_plugin import (
    ActionContext,
    Context,
    CopyParams,
    CopyType,
    PluginInitParams,
    Query,
    Result,
    ResultAction,
    UpdatableResult,
    WoxImage,
    WoxPreview,
    WoxPreviewType,
)


DEFAULT_BASE_URL = "http://127.0.0.1:8642"
DEFAULT_API_KEY = "change-me-local-dev"
CONVERSATION_NAME = "wox"
QUICK_PREFIX = "请用简洁中文回答，除非任务确实需要详细步骤。用户请求："
REMINDER_KEYWORDS = ("提醒事项", "提醒", "remind", "reminder", "reminders", "todo", "待办")
AGENT_KEYWORDS = (
    "执行",
    "修改",
    "创建",
    "安装",
    "运行",
    "打开",
    "搜索",
    "查找",
    "网页",
    "项目",
    "仓库",
    "文件",
    "修复",
    "分析这个项目",
    "多步骤",
)


def _config() -> tuple[str, str]:
    base_url = os.getenv("HERMES_API_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    api_key = os.getenv("HERMES_API_KEY", DEFAULT_API_KEY)
    return base_url, api_key


def _request_json(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    base_url, api_key = _config()
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}{path}",
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=90) as res:
        return json.loads(res.read().decode("utf-8"))


def _extract_response_text(data: dict[str, Any]) -> str:
    if isinstance(data.get("output_text"), str):
        return data["output_text"].strip()

    chunks: list[str] = []
    for item in data.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and isinstance(content.get("text"), str):
                chunks.append(content["text"])

    if chunks:
        return "\n".join(chunks).strip()

    return json.dumps(data, ensure_ascii=False, indent=2)


def _shorten(text: str, limit: int = 140) -> str:
    single_line = " ".join(text.split())
    if len(single_line) <= limit:
        return single_line
    return f"{single_line[: limit - 1]}..."


def _read_open_reminders() -> list[dict[str, str]]:
    script = """
set output to ""
tell application "Reminders"
    repeat with l in lists
        set listName to name of l
        repeat with r in reminders of l whose completed is false
            set reminderName to name of r
            set dueText to ""
            try
                set dueText to due date of r as string
            end try
            set output to output & reminderName & tab & listName & tab & dueText & linefeed
            if (count paragraphs of output) > 30 then return output
        end repeat
    end repeat
end tell
return output
"""
    proc = subprocess.run(
        ["osascript", "-e", script],
        text=True,
        capture_output=True,
        timeout=8,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "osascript failed")

    reminders: list[dict[str, str]] = []
    for line in proc.stdout.splitlines():
        parts = line.split("\t")
        if not parts or not parts[0].strip():
            continue
        reminders.append(
            {
                "title": parts[0].strip(),
                "list": parts[1].strip() if len(parts) > 1 else "",
                "due": parts[2].strip() if len(parts) > 2 else "",
            }
        )
    return reminders


def _format_reminders(reminders: list[dict[str, str]], command: str) -> str:
    if not reminders:
        return "### 未完成提醒事项\n\n没有未完成的 Apple 提醒事项。"

    lines = ["### 未完成提醒事项", ""]
    if "今天" in command:
        lines.append("> 当前版本先列出全部未完成事项；下一版可以继续细分今天/逾期。")
        lines.append("")

    for index, item in enumerate(reminders[:30], start=1):
        meta = []
        if item["list"]:
            meta.append(item["list"])
        if item["due"]:
            meta.append(item["due"])
        suffix = f"（{' · '.join(meta)}）" if meta else ""
        lines.append(f"{index}. {item['title']}{suffix}")

    if len(reminders) > 30:
        lines.append("")
        lines.append(f"还有 {len(reminders) - 30} 条未显示。")

    return "\n".join(lines)


class HermesPlugin:
    async def init(self, ctx: Context, params: PluginInitParams) -> None:
        self.api = params.api
        self.last_response = ""

    async def query(self, ctx: Context, query: Query) -> list[Result]:
        command = self._command_text(query)

        if not command:
            return [
                Result(
                    title="Hermes",
                    sub_title="输入指令后按 Enter 发送，例如：hermes 总结当前剪贴板内容",
                    icon=WoxImage.new_emoji("🪽"),
                    score=100,
                )
            ]

        if command.lower() in {"status", "health"}:
            return await self._status_results()

        route, routed_command = self._route_command(command)
        if route == "reminders":
            return [self._reminders_result(routed_command)]

        return [self._send_result(routed_command, route)]

    def _command_text(self, query: Query) -> str:
        if query.search.strip():
            return query.search.strip()

        raw = query.raw_query.strip()
        trigger = query.trigger_keyword.strip()
        if trigger and raw.lower().startswith(trigger.lower()):
            return raw[len(trigger) :].strip()

        return " ".join(part for part in [query.command.strip(), query.search.strip()] if part).strip()

    async def _status_results(self) -> list[Result]:
        try:
            data = await asyncio.to_thread(_request_json, "GET", "/v1/health")
            status = data.get("status", "unknown")
            platform = data.get("platform", "hermes-agent")
            return [
                Result(
                    title=f"Hermes 在线：{status}",
                    sub_title=f"{platform} at {_config()[0]}",
                    icon=WoxImage.new_emoji("🪽"),
                    score=100,
                )
            ]
        except Exception as exc:
            return [self._error_result(exc)]

    def _route_command(self, command: str) -> tuple[str, str]:
        lowered = command.lower().strip()

        for prefix in ("q ", "quick ", "快问 "):
            if lowered.startswith(prefix):
                return "quick", command[len(prefix) :].strip()

        for prefix in ("agent ", "代理 "):
            if lowered.startswith(prefix):
                return "agent", command[len(prefix) :].strip()

        if lowered.startswith("full "):
            return "full", command[5:].strip()

        if any(keyword in lowered for keyword in REMINDER_KEYWORDS):
            return "reminders", command

        if any(keyword in command for keyword in AGENT_KEYWORDS):
            return "agent", command

        return "quick", command

    def _route_label(self, route: str) -> str:
        return {
            "quick": "快速问答",
            "agent": "Hermes Agent",
            "full": "完整深度模式",
        }.get(route, "Hermes")

    def _send_result(self, command: str, route: str) -> Result:
        mode = self._route_label(route)
        display_command = command
        return Result(
            id="hermes-send",
            title=f"发送给 Hermes：{_shorten(display_command, 72)}",
            sub_title=f"{mode}，按 Enter 发送；回复会直接显示在 Wox 里",
            icon=WoxImage.new_emoji("🪽"),
            preview=WoxPreview(
                preview_type=WoxPreviewType.MARKDOWN,
                preview_data=f"### 即将发送\n\n{display_command}",
            ),
            score=100,
            actions=[
                ResultAction(
                    id="send",
                    name="发送给 Hermes",
                    icon=WoxImage.new_emoji("↩️"),
                    is_default=True,
                    prevent_hide_after_action=True,
                    action=lambda action_ctx, result_ctx: self._start_command(action_ctx, command, route),
                ),
                ResultAction(
                    id="copy-last",
                    name="复制上一次回复",
                    icon=WoxImage.new_emoji("📋"),
                    action=lambda action_ctx, result_ctx: self._copy_last_response(action_ctx),
                )
            ],
        )

    def _reminders_result(self, command: str) -> Result:
        return Result(
            id="hermes-reminders",
            title="读取 Apple 提醒事项",
            sub_title="本地快速通道，按 Enter 查看未完成事项",
            icon=WoxImage.new_emoji("✅"),
            preview=WoxPreview(
                preview_type=WoxPreviewType.MARKDOWN,
                preview_data=f"### 本地提醒事项\n\n{command}",
            ),
            score=110,
            actions=[
                ResultAction(
                    id="read-reminders",
                    name="读取未完成提醒事项",
                    icon=WoxImage.new_emoji("✅"),
                    is_default=True,
                    prevent_hide_after_action=True,
                    action=lambda action_ctx, result_ctx: self._start_reminders(action_ctx, command),
                ),
                ResultAction(
                    id="copy-last",
                    name="复制上一次回复",
                    icon=WoxImage.new_emoji("📋"),
                    action=lambda action_ctx, result_ctx: self._copy_last_response(action_ctx),
                ),
            ],
        )

    async def _start_command(self, ctx: Context, command: str, route: str) -> None:
        if isinstance(ctx, ActionContext):
            result_id = ctx.result_id
        else:
            result_id = "hermes-send"
        await self.api.update_result(
            ctx,
            UpdatableResult(
                id=result_id,
                title="Hermes 正在处理...",
                sub_title=_shorten(command, 180),
                icon=WoxImage.new_emoji("⏳"),
                preview=WoxPreview(
                    preview_type=WoxPreviewType.MARKDOWN,
                    preview_data=f"### {self._route_label(route)}正在处理\n\n{command}",
                ),
            ),
        )
        asyncio.create_task(self._ask_and_show(ctx, result_id, command, route))

    async def _ask_and_show(self, ctx: Context, result_id: str, command: str, route: str) -> None:
        try:
            input_text = command if route in {"agent", "full"} else f"{QUICK_PREFIX}{command}"
            data = await asyncio.to_thread(
                _request_json,
                "POST",
                "/v1/responses",
                {
                    "model": "hermes-agent",
                    "input": input_text,
                    "store": True,
                    "conversation": CONVERSATION_NAME,
                },
            )
            text = _extract_response_text(data)
            self.last_response = text
            await self.api.update_result(
                ctx,
                UpdatableResult(
                    id=result_id,
                    title=_shorten(text, 86) or "Hermes 已返回结果",
                    sub_title=_shorten(text, 220),
                    icon=WoxImage.new_emoji("🪽"),
                    preview=WoxPreview(
                        preview_type=WoxPreviewType.MARKDOWN,
                        preview_data=text,
                    ),
                ),
            )
        except Exception as exc:
            message = self._error_message(exc)
            await self.api.update_result(
                ctx,
                UpdatableResult(
                    id=result_id,
                    title="Hermes 调用失败",
                    sub_title=_shorten(message, 220),
                    icon=WoxImage.new_emoji("⚠️"),
                    preview=WoxPreview(
                        preview_type=WoxPreviewType.TEXT,
                        preview_data=message,
                    ),
                ),
            )

    async def _start_reminders(self, ctx: Context, command: str) -> None:
        result_id = ctx.result_id if isinstance(ctx, ActionContext) else "hermes-reminders"
        await self.api.update_result(
            ctx,
            UpdatableResult(
                id=result_id,
                title="正在读取 Apple 提醒事项...",
                sub_title="如果 macOS 弹出权限请求，请允许 Wox 访问提醒事项",
                icon=WoxImage.new_emoji("⏳"),
                preview=WoxPreview(
                    preview_type=WoxPreviewType.MARKDOWN,
                    preview_data="### 正在读取 Apple 提醒事项\n\n首次使用可能需要在系统弹窗里授权。",
                ),
            ),
        )
        asyncio.create_task(self._read_reminders_and_show(ctx, result_id, command))

    async def _read_reminders_and_show(self, ctx: Context, result_id: str, command: str) -> None:
        try:
            reminders = await asyncio.to_thread(_read_open_reminders)
            text = _format_reminders(reminders, command)
            self.last_response = text
            await self.api.update_result(
                ctx,
                UpdatableResult(
                    id=result_id,
                    title=_shorten(text, 86),
                    sub_title=f"{len(reminders)} 条未完成提醒事项",
                    icon=WoxImage.new_emoji("✅"),
                    preview=WoxPreview(
                        preview_type=WoxPreviewType.MARKDOWN,
                        preview_data=text,
                    ),
                ),
            )
        except Exception as exc:
            message = self._error_message(exc)
            await self.api.update_result(
                ctx,
                UpdatableResult(
                    id=result_id,
                    title="读取提醒事项失败",
                    sub_title=_shorten(message, 220),
                    icon=WoxImage.new_emoji("⚠️"),
                    preview=WoxPreview(
                        preview_type=WoxPreviewType.TEXT,
                        preview_data=message,
                    ),
                ),
            )

    async def _copy_last_response(self, ctx: Context) -> None:
        if not self.last_response:
            await self.api.notify(ctx, "还没有可复制的 Hermes 回复")
            return
        await self.api.copy(ctx, CopyParams(type=CopyType.TEXT, text=self.last_response))
        await self.api.notify(ctx, "Hermes 回复已复制")

    def _error_result(self, exc: Exception) -> Result:
        message = self._error_message(exc)
        return Result(
            title="Hermes 调用失败",
            sub_title=_shorten(message, 220),
            icon=WoxImage.new_emoji("⚠️"),
            score=100,
        )

    def _error_message(self, exc: Exception) -> str:
        if isinstance(exc, urllib.error.HTTPError):
            try:
                return exc.read().decode("utf-8")
            except Exception:
                return str(exc)
        return str(exc)


plugin = HermesPlugin()
