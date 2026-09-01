"""Provider-neutral prompt construction for campus-message analysis."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from app.models import Message, Sender
from app.schemas.ai import CandidateInformation

SYSTEM_PROMPT = """你是 UniBrief 的校园消息分析器。只输出一个 JSON 对象，不要 Markdown，不要解释。
顶层只能包含 useful 和 items。useful=false 时 items 必须为空；useful=true 时至少一个 item。
每个 item 必须包含 action、target_information_id、relation_type、title、summary、
source_type、importance、confidence、categories、tags、event。
action 矩阵：create/null/CREATE；link/候选ID/SUPPORT；
update/候选ID/UPDATE；correct/候选ID/CORRECTION。
不得引用候选列表外 ID，不得对同一 target 输出多个写操作。
importance 为 1..5，confidence 为 0..1。
event 为 null，或包含带时区 ISO 8601 的 start_at/deadline（至少一个非 null）
及 status=UPCOMING。
只提取对用户有行动、安排、截止时间、重要通知或可复用事实价值的信息；
普通闲聊、表情和无信息量回复设为 useful=false。
link 只表示补充证据；update 表示新信息更新原事项；correct 表示纠正原信息；
没有合适候选时 create。"""

def build_analysis_messages(
    message: Message,
    sender: Sender,
    candidates: list[CandidateInformation],
) -> list[dict[str, str]]:
    """Build a deterministic JSON user payload without mixing users."""

    payload = {
        "current_time": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "message": {
            "id": message.id,
            "content": message.content,
            "sent_at": message.sent_at.replace(tzinfo=UTC).isoformat().replace("+00:00", "Z"),
            "sender": {
                "display_name": sender.display_name,
                "source_type": sender.source_type,
                "credibility": float(sender.credibility),
            },
        },
        "candidate_information": [item.model_dump(mode="json") for item in candidates],
    }
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        },
    ]

