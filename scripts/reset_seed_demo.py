"""Reset the configured database and load deterministic synthetic demo data."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))
os.chdir(BACKEND_ROOT)

from sqlalchemy import select, text  # noqa: E402
from sqlalchemy.exc import SQLAlchemyError  # noqa: E402

from app.core.enums import (  # noqa: E402
    AnalysisStatus,
    AttachmentStatus,
    DictionaryStatus,
    EventStatus,
    InformationStatus,
    MessageStatus,
    RelationType,
    ReminderStatus,
)
from app.core.security import hash_password  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.models import (  # noqa: E402
    AIAnalysis,
    Category,
    Channel,
    Event,
    EventReminder,
    InformationCategory,
    InformationItem,
    InformationTag,
    Message,
    MessageAttachment,
    MessageInformation,
    Platform,
    Sender,
    Tag,
    User,
)

CORE_TABLES = [
    "event_reminder",
    "event",
    "information_tag",
    "information_category",
    "message_information",
    "ai_analysis",
    "message_attachment",
    "message",
    "tag",
    "information_item",
    "sender",
    "channel",
    "platform",
    "category",
    "user",
    "system_setting",
]
SEED_CATEGORIES = [
    ("课程", "课程安排与教学信息"),
    ("作业", "作业、报告与提交要求"),
    ("考试", "考试、测验与复习安排"),
    ("活动", "校园活动与社团通知"),
    ("通知", "行政及综合通知"),
    ("其他", "暂未归入其他分类的信息"),
]
DEMO_PASSWORD = "DemoStudent2026!"
OBSERVER_PASSWORD = "DemoObserver2026!"
BASE_TIME = datetime(2026, 9, 1, 1, 0)
COURSE_TITLES = [
    "数据库课程设计初稿提交",
    "数据库实验报告提交",
    "操作系统作业提交",
    "计算机组成原理 Quiz",
    "数据结构上机考试",
    "软件工程需求文档评审",
    "算法竞赛训练报名",
    "大学英语口语展示",
    "高等数学期中测验",
    "概率论习题课调整",
    "线性代数答疑安排",
    "体育健康测试",
]
ACTIVITY_TITLES = [
    "校园歌手大赛报名",
    "编程马拉松报名",
    "志愿服务时长补录",
    "社团招新截止",
    "篮球联赛报名",
    "图书馆读书分享会",
    "校庆志愿者招募",
    "心理健康讲座报名",
    "创新创业大赛初赛",
    "机器人竞赛组队",
    "辩论赛淘汰赛",
    "摄影展投稿",
]
CAREER_TITLES = [
    "秋季校园宣讲会预约",
    "内推材料提交",
    "简历门诊预约",
    "实习证明归档",
]
NOTICE_TITLES = [
    "综合测评材料提交",
    "奖学金申请截止",
    "宿舍安全检查",
    "医保信息确认",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force", action="store_true", help="确实清空并重建当前 DATABASE_URL 指向的数据"
    )
    return parser.parse_args()


def reset_database(force: bool) -> None:
    if not force:
        raise SystemExit("Refusing to reset without --force.")
    with engine.connect() as connection:
        database = connection.execute(text("SELECT DATABASE()")).scalar_one()
        if database not in {"unibrief", "unibrief_test"}:
            raise SystemExit(f"Refusing to reset unexpected database: {database}")
        connection.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for table in CORE_TABLES:
            connection.execute(text(f"TRUNCATE TABLE `{table}`"))
        connection.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        connection.execute(
            text(
                """
            INSERT INTO system_setting
                (setting_key, value_text, value_type, is_sensitive, description)
            VALUES
                ('registration_enabled', 'false', 'BOOLEAN', 0, '是否允许普通用户自助注册'),
                ('admin_session_version', '1', 'INTEGER', 1, '管理员会话失效版本')
            """
            )
        )
        connection.execute(
            text(
                "INSERT INTO category (name, description, status) "
                "VALUES (:name, :description, 'ACTIVE')"
            ),
            [{"name": name, "description": description} for name, description in SEED_CATEGORIES],
        )
        connection.commit()


def reset_attachment_files() -> None:
    from app.core.config import get_settings

    root = get_settings().attachment_storage_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    for child in root.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def seed() -> dict[str, int]:
    with SessionLocal() as db:
        demo = User(
            username="demo_student",
            display_name="演示学生",
            password_hash=hash_password(DEMO_PASSWORD),
            last_login_at=None,
        )
        observer = User(
            username="demo_observer",
            display_name="隔离演示用户",
            password_hash=hash_password(OBSERVER_PASSWORD),
        )
        db.add_all([demo, observer])
        db.flush()
        platforms: dict[str, Platform] = {}
        for name, platform_type in (
            ("QQ", "IM"),
            ("WeChat", "IM"),
            ("DingTalk", "IM"),
        ):
            platform = Platform(name=name, type=platform_type, status=DictionaryStatus.ACTIVE.value)
            db.add(platform)
            db.flush()
            platforms[name] = platform
        categories = {
            category.name: category for category in db.scalars(select(Category))
        }
        channels: list[Channel] = []
        for platform in platforms.values():
            for index in range(1, 4):
                channel = Channel(
                    user_id=demo.id,
                    platform_id=platform.id,
                    external_id=f"{platform.name.lower()}-class-{index:03d}",
                    name=f"{platform.name} 课程群 {index}",
                    channel_type="GROUP",
                )
                channels.append(channel)
                db.add(channel)
        observer_channel = Channel(
            user_id=observer.id,
            platform_id=platforms["QQ"].id,
            external_id="observer-group",
            name="隔离演示群",
            channel_type="GROUP",
        )
        db.add(observer_channel)
        db.flush()
        senders: list[Sender] = []
        sender_specs = [
            ("teacher", "张老师", "TEACHER", "0.950"),
            ("leader", "李班长", "CLASS_LEADER", "0.800"),
            ("student", "王同学", "STUDENT", "0.500"),
            ("admin", "教务通知", "ADMIN", "0.980"),
        ]
        for platform in platforms.values():
            for suffix, display_name, source_type, credibility in sender_specs:
                sender = Sender(
                    user_id=demo.id,
                    platform_id=platform.id,
                    external_id=f"{platform.name.lower()}-{suffix}",
                    display_name=display_name,
                    source_type=source_type,
                    credibility=Decimal(credibility),
                )
                senders.append(sender)
                db.add(sender)
        observer_sender = Sender(
            user_id=observer.id,
            platform_id=platforms["QQ"].id,
            external_id="observer-sender",
            display_name="隔离演示发送者",
            source_type="STUDENT",
            credibility=Decimal("0.500"),
        )
        db.add(observer_sender)
        db.flush()

        all_titles = COURSE_TITLES + ACTIVITY_TITLES + CAREER_TITLES + NOTICE_TITLES
        category_names = (
            ["作业"] * 6 + ["课程"] * 3 + ["考试"] * 3 + ["活动"] * 12 + ["通知"] * 4 + ["其他"] * 4
        )
        tag_names = [
            "数据库",
            "课程设计",
            "考试",
            "活动",
            "报名",
            "截止",
            "就业",
            "综测",
            "校园",
            "通知",
        ]
        tag_objects: dict[str, Tag] = {}
        for tag_name in tag_names:
            tag = Tag(user_id=demo.id, name=tag_name)
            db.add(tag)
            tag_objects[tag_name] = tag
        observer_tag = Tag(user_id=observer.id, name="隔离演示")
        db.add(observer_tag)
        db.flush()

        information_rows: list[InformationItem] = []
        information_specs: list[tuple[str, str, str, int]] = []
        for index, title in enumerate(all_titles):
            category_name = category_names[index]
            source_type = "TEACHER" if category_name in {"作业", "课程", "考试"} else "ADMIN"
            importance = 5 if category_name in {"作业", "考试"} else 4
            summary = f"{title}。请在截止时间前完成并按要求提交，后续消息会补充或更正具体安排。"
            information = InformationItem(
                user_id=demo.id,
                title=title,
                summary=summary,
                source_type=source_type,
                importance=importance,
                confidence=Decimal("0.920"),
                status=InformationStatus.UPDATED.value,
                version=3,
                created_at=BASE_TIME + timedelta(hours=index),
                updated_at=BASE_TIME + timedelta(hours=index, minutes=45),
            )
            db.add(information)
            information_rows.append(information)
            information_specs.append((category_name, title, source_type, importance))

        observer_information = [
            InformationItem(
                user_id=observer.id,
                title="隔离演示事项一",
                summary="只属于隔离演示用户。",
                source_type="STUDENT",
                importance=3,
                confidence=Decimal("0.800"),
                created_at=BASE_TIME,
                updated_at=BASE_TIME,
                version=1,
            ),
            InformationItem(
                user_id=observer.id,
                title="隔离演示事项二",
                summary="用于验证跨用户不可见。",
                source_type="STUDENT",
                importance=2,
                confidence=Decimal("0.700"),
                created_at=BASE_TIME + timedelta(minutes=10),
                updated_at=BASE_TIME + timedelta(minutes=10),
                version=1,
            ),
        ]
        db.add_all(observer_information)
        db.flush()

        relation_rows = 0
        message_count = 0
        attachments: list[tuple[MessageAttachment, bytes | None]] = []
        failed_messages: list[Message] = []
        for info_index, (information, spec) in enumerate(
            zip(information_rows, information_specs, strict=True)
        ):
            category_name, title, source_type, importance = spec
            db.add(
                InformationCategory(
                    information_id=information.id, category_id=categories[category_name].id
                )
            )
            selected_tags = [
                tag_objects[name] for name in tag_names[(info_index % 6) : ((info_index % 6) + 3)]
            ]
            for tag in selected_tags:
                db.add(
                    InformationTag(user_id=demo.id, information_id=information.id, tag_id=tag.id)
                )
            sent_at = BASE_TIME + timedelta(hours=info_index * 4, minutes=7)
            relation_specs = [
                (RelationType.CREATE.value, "发布通知：", MessageStatus.PROCESSED.value),
                (RelationType.SUPPORT.value, "补充说明：", MessageStatus.PROCESSED.value),
                (
                    RelationType.SUPPORT.value,
                    "收到，确认截止时间是：",
                    MessageStatus.PROCESSED.value,
                ),
                (RelationType.SUPPORT.value, "提醒大家注意：", MessageStatus.PROCESSED.value),
                (RelationType.UPDATE.value, "更新安排：", MessageStatus.PROCESSED.value),
                (RelationType.CORRECTION.value, "更正时间：", MessageStatus.PROCESSED.value),
                (RelationType.SUPPORT.value, "最终确认：", MessageStatus.PROCESSED.value),
            ]
            for relation_index, (relation_type, prefix, status) in enumerate(relation_specs):
                channel = channels[(info_index + relation_index) % len(channels)]
                sender = senders[(info_index * 3 + relation_index) % len(senders)]
                message = Message(
                    user_id=demo.id,
                    channel_id=channel.id,
                    sender_id=sender.id,
                    external_id=f"demo-info-{info_index:03d}-{relation_index}",
                    content=f"{prefix}{title}。请以最新通知为准。",
                    sent_at=sent_at + timedelta(minutes=relation_index * 9),
                    ingested_at=sent_at + timedelta(minutes=relation_index * 9),
                    process_status=status,
                )
                db.add(message)
                db.flush()
                db.add(
                    MessageInformation(
                        user_id=demo.id,
                        message_id=message.id,
                        information_id=information.id,
                        relation_type=relation_type,
                    )
                )
                relation_rows += 1
                message_count += 1
                if relation_index == 0:
                    db.add(
                        AIAnalysis(
                            message_id=message.id,
                            model_name="synthetic-seed-v1",
                            status=AnalysisStatus.SUCCEEDED.value,
                            useful=True,
                            latency_ms=820,
                            raw_result={"source": "synthetic_seed"},
                            raw_response_text=json.dumps(
                                {"source": "synthetic_seed"}, ensure_ascii=False
                            ),
                            analyzed_at=sent_at,
                        )
                    )
                if info_index < 12 and relation_index == 1:
                    payload = f"合成附件 {info_index:02d}\n".encode()
                    digest = hashlib.sha256(payload).hexdigest()
                    storage_key = f"seed/{info_index:02d}/{digest}.txt"
                    root = Path("./var/attachments").resolve()
                    (root / storage_key).parent.mkdir(parents=True, exist_ok=True)
                    (root / storage_key).write_bytes(payload)
                    attachments.append(
                        (
                            MessageAttachment(
                                message_id=message.id,
                                external_id=f"demo-file-{info_index:02d}",
                                file_type="text/plain",
                                file_name=f"notice-{info_index:02d}.txt",
                                file_url=f"https://files.example.com/unibrief/{digest}.txt",
                                storage_key=storage_key,
                                file_size=len(payload),
                                sha256=digest,
                                download_status=AttachmentStatus.DOWNLOADED.value,
                                download_attempts=1,
                                downloaded_at=sent_at,
                            ),
                            None,
                        )
                    )
                if 12 <= info_index < 24 and relation_index == 1:
                    attachments.append(
                        (
                            MessageAttachment(
                                message_id=message.id,
                                external_id=f"demo-failed-{info_index:02d}",
                                file_type="application/pdf",
                                file_name=f"failed-{info_index:02d}.pdf",
                                file_url=f"https://files.example.com/timeout/{info_index}.pdf",
                                storage_key=None,
                                file_size=None,
                                sha256=None,
                                download_status=AttachmentStatus.FAILED.value,
                                download_attempts=3,
                                last_error="TIMEOUT",
                            ),
                            None,
                        )
                    )

        for information in observer_information:
            for index in range(7):
                message = Message(
                    user_id=observer.id,
                    channel_id=observer_channel.id,
                    sender_id=observer_sender.id,
                    external_id=f"observer-info-{information.id}-{index}",
                    content=f"隔离演示消息 {index}：{information.title}",
                    sent_at=BASE_TIME + timedelta(minutes=index),
                    ingested_at=BASE_TIME + timedelta(minutes=index),
                    process_status=MessageStatus.PROCESSED.value,
                )
                db.add(message)
                db.flush()
                db.add(
                    MessageInformation(
                        user_id=observer.id,
                        message_id=message.id,
                        information_id=information.id,
                        relation_type=RelationType.CREATE.value
                        if index == 0
                        else RelationType.SUPPORT.value,
                    )
                )
                relation_rows += 1
                message_count += 1

        chat_samples = [
            "哈哈哈",
            "收到",
            "谢谢老师",
            "去食堂吗",
            "下午打球吗",
            "表情包",
            "这边也有人",
            "刚看到",
            "顶一下",
            "确实",
            "好的",
            "在图书馆",
        ]
        for index in range(720):
            channel = channels[index % len(channels)]
            sender = senders[index % len(senders)]
            message = Message(
                user_id=demo.id,
                channel_id=channel.id,
                sender_id=sender.id,
                external_id=f"demo-chat-{index:04d}",
                content=f"{chat_samples[index % len(chat_samples)]}（合成闲聊 {index:04d}）",
                sent_at=BASE_TIME + timedelta(minutes=index * 11),
                ingested_at=BASE_TIME + timedelta(minutes=index * 11),
                process_status=MessageStatus.IGNORED.value,
            )
            db.add(message)
            db.flush()
            if index < 120:
                db.add(
                    AIAnalysis(
                        message_id=message.id,
                        model_name="synthetic-seed-v1",
                        status=AnalysisStatus.SUCCEEDED.value,
                        useful=False,
                        latency_ms=310,
                        raw_result={"source": "synthetic_seed", "useful": False, "items": []},
                        raw_response_text='{"useful":false,"items":[]}',
                        analyzed_at=BASE_TIME + timedelta(minutes=index * 11, seconds=2),
                    )
                )
            message_count += 1

        for index in range(24):
            channel = channels[(index + 5) % len(channels)]
            sender = senders[(index + 11) % len(senders)]
            message = Message(
                user_id=demo.id,
                channel_id=channel.id,
                sender_id=sender.id,
                external_id=f"demo-ai-failed-{index:02d}",
                content=f"AI 边界样例 {index:02d}：请输出不完整 JSON，用于验证失败重试。",
                sent_at=BASE_TIME + timedelta(hours=8, minutes=index),
                ingested_at=BASE_TIME + timedelta(hours=8, minutes=index),
                process_status=MessageStatus.FAILED.value,
                processing_started_at=None,
            )
            db.add(message)
            db.flush()
            db.add(
                AIAnalysis(
                    message_id=message.id,
                    model_name="synthetic-boundary-model",
                    status=AnalysisStatus.FAILED.value,
                    useful=None,
                    error_code="INVALID_AI_OUTPUT",
                    error_message="AI 返回内容不是符合约定的 JSON",
                    latency_ms=640,
                    raw_response_text='{"useful":true',
                    analyzed_at=BASE_TIME + timedelta(hours=8, minutes=index, seconds=3),
                )
            )
            failed_messages.append(message)
            message_count += 1

        for index in range(24):
            channel = channels[(index + 2) % len(channels)]
            sender = senders[(index + 7) % len(senders)]
            message = Message(
                user_id=demo.id,
                channel_id=channel.id,
                sender_id=sender.id,
                external_id=f"demo-pending-{index:02d}",
                content=f"待真实 AI 分析样例 {index:02d}：数据库课程设计演示材料提交安排。",
                sent_at=BASE_TIME + timedelta(hours=16, minutes=index),
                ingested_at=BASE_TIME + timedelta(hours=16, minutes=index),
                process_status=MessageStatus.PENDING.value,
            )
            db.add(message)
            message_count += 1

        for attachment, _ in attachments:
            db.add(attachment)
        db.flush()

        event_count = 0
        now = datetime.now(UTC).replace(tzinfo=None)
        for index, information in enumerate(information_rows):
            if index >= 24:
                break
            start_at = BASE_TIME + timedelta(days=index + 3, hours=2)
            deadline = start_at + timedelta(hours=8)
            event_status = (
                EventStatus.UPCOMING.value if deadline > now else EventStatus.EXPIRED.value
            )
            event = Event(
                information_id=information.id,
                start_at=start_at,
                deadline=deadline,
                event_status=event_status,
            )
            db.add(event)
            db.flush()
            remind_at = deadline - timedelta(hours=24)
            reminder_status = (
                ReminderStatus.DUE.value if remind_at <= now else ReminderStatus.PENDING.value
            )
            db.add(
                EventReminder(
                    event_id=event.id,
                    remind_at=remind_at,
                    reminder_status=reminder_status,
                    is_custom_time=index % 7 == 0,
                )
            )
            event_count += 1
        db.commit()
        return {
            "users": 2,
            "platforms": len(platforms),
            "channels": len(channels) + 1,
            "senders": len(senders) + 1,
            "messages": message_count,
            "information_items": len(information_rows) + len(observer_information),
            "message_information": relation_rows,
            "events": event_count,
            "event_reminders": event_count,
            "attachments": len(attachments),
        }


def _count_seed() -> dict[str, int]:
    """Return the deterministic seed totals without touching the database."""

    demo_messages = 32 * 7 + 720 + 24 + 24
    observer_messages = 2 * 7
    relation_rows = 32 * 7 + 2 * 7
    return {
        "users": 2,
        "platforms": 3,
        "channels": 10,
        "senders": 13,
        "messages": demo_messages + observer_messages,
        "information_items": 32 + 2,
        "message_information": relation_rows,
        "events": 24,
        "event_reminders": 24,
        "attachments": 24,
    }

def main() -> int:
    args = parse_args()
    try:
        reset_database(args.force)
        reset_attachment_files()
        counts = seed()
    except (SQLAlchemyError, OSError) as exc:
        print(f"seed failed: {type(exc).__name__}", file=sys.stderr)
        return 1
    print(json.dumps({"status": "ok", "counts": counts}, ensure_ascii=False, indent=2))
    print("demo username: demo_student")
    print("demo password: DemoStudent2026!")
    print("observer username: demo_observer")
    print("observer password: DemoObserver2026!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())





