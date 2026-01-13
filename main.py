import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_URL = os.getenv("CHANNEL_URL", "https://t.me/your_channel")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is required. Set it in .env or environment variables.")

logging.basicConfig(level=logging.INFO)

STEAK_CUTS = [
    "Рибай",
    "Стриплойн",
    "Ти-бон",
    "Томагавк",
    "Сирлойн",
    "Филе-миньон",
    "Фланк",
    "Скёрт",
    "Денвер",
]

PARTS = {
    "Тонкий край": "Стриплойн",
    "Толстый край": "Рибай",
    "Вырезка": "Филе-миньон",
    "Лопатка": "Денвер",
    "Грудинка": "Фланк",
    "Пашина": "Скёрт",
    "Шея": "Сирлойн",
}

DONENESS = [
    "Rare / Medium Rare",
    "Medium",
    "Medium Well",
    "Well Done",
]

STAGES = [
    {
        "title": "Подготовка",
        "text": "Достаньте мясо из холодильника за 30–40 минут. Промокните бумажным полотенцем, посолите и поперчите.",
    },
    {
        "title": "Разогрев",
        "text": "Разогрейте сковороду до уверенно горячего состояния. Капля воды должна быстро испаряться.",
    },
    {
        "title": "Обжарка",
        "text": "Обжарьте стейк с каждой стороны по 2–4 минуты (зависит от толщины) и добавьте сливочное масло/чеснок по желанию.",
    },
    {
        "title": "Отдых",
        "text": "Переложите мясо на тарелку и дайте отдохнуть 5–7 минут, чтобы соки распределились.",
    },
    {
        "title": "Подача",
        "text": "Нарежьте поперёк волокон, добавьте соль и соус по вкусу.",
    },
]


@dataclass
class Session:
    path: str
    cut: Optional[str] = None
    part: Optional[str] = None
    doneness: Optional[str] = None
    stage_index: int = 0
    history: List[str] = field(default_factory=list)


sessions: Dict[int, Session] = {}


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="У меня есть кусок мяса (стейк)", callback_data="path:steak")],
            [InlineKeyboardButton(text="У меня есть конкретная часть туши", callback_data="path:part")],
        ]
    )


def list_keyboard(items: List[str], prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=item, callback_data=f"{prefix}:{index}")]
            for index, item in enumerate(items)
        ]
    )


def doneness_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=item, callback_data=f"doneness:{index}")]
            for index, item in enumerate(DONENESS)
        ]
    )


def next_stage_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Дальше", callback_data="stage:next")]]
    )


def finish_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Вступить в TG канал", url=CHANNEL_URL)],
            [InlineKeyboardButton(text="Начать заново", callback_data="restart")],
        ]
    )


def format_intro(session: Session) -> str:
    details = []
    if session.cut:
        details.append(f"Стейк: {session.cut}")
    if session.part:
        details.append(f"Часть туши: {session.part}")
    if session.doneness:
        details.append(f"Прожарка: {session.doneness}")
    suffix = "\n".join(details)
    if suffix:
        return f"Отлично!\n{suffix}"
    return "Отлично!"


def stage_message(session: Session) -> str:
    stage = STAGES[session.stage_index]
    return f"<b>Этап {session.stage_index + 1} — {stage['title']}</b>\n{stage['text']}"


def start_session(user_id: int, path: str) -> Session:
    session = Session(path=path)
    sessions[user_id] = session
    return session


async def cmd_start(message: Message) -> None:
    text = (
        "Вы попали в Бифы в интернете. С чего хотите начать?\n\n"
        "Выберите путь ниже:"
    )
    await message.answer(text, reply_markup=main_menu_keyboard())


async def select_path(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    path = callback.data.split(":", 1)[1]
    start_session(user_id, path)
    if path == "steak":
        await callback.message.answer(
            "Выберите стейк, с которым хотите работать:",
            reply_markup=list_keyboard(STEAK_CUTS, "cut"),
        )
    else:
        await callback.message.answer(
            "Выберите часть туши:",
            reply_markup=list_keyboard(list(PARTS.keys()), "part"),
        )
    await callback.answer()


async def select_cut(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    index = int(callback.data.split(":", 1)[1])
    session = sessions.get(user_id)
    if not session:
        await callback.answer("Начните с /start")
        return
    session.cut = STEAK_CUTS[index]
    await callback.message.answer(
        f"Вы выбрали: {session.cut}. Теперь выберите прожарку:",
        reply_markup=doneness_keyboard(),
    )
    await callback.answer()


async def select_part(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    index = int(callback.data.split(":", 1)[1])
    part = list(PARTS.keys())[index]
    session = sessions.get(user_id)
    if not session:
        await callback.answer("Начните с /start")
        return
    session.part = part
    suggested_cut = PARTS[part]
    await callback.message.answer(
        f"Часть туши: {part}. Обычно из неё делают: {suggested_cut}.\n"
        "Хотите выбрать прожарку?",
        reply_markup=doneness_keyboard(),
    )
    await callback.answer()


async def select_doneness(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    index = int(callback.data.split(":", 1)[1])
    session = sessions.get(user_id)
    if not session:
        await callback.answer("Начните с /start")
        return
    session.doneness = DONENESS[index]
    session.stage_index = 0
    intro = format_intro(session)
    await callback.message.answer(intro)
    await callback.message.answer(stage_message(session), reply_markup=next_stage_keyboard())
    await callback.answer()


async def next_stage(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    session = sessions.get(user_id)
    if not session:
        await callback.answer("Начните с /start")
        return
    session.stage_index += 1
    if session.stage_index >= len(STAGES):
        await callback.message.answer(
            "Готово! Если хотите больше подсказок, загляните в наш канал.",
            reply_markup=finish_keyboard(),
        )
        await callback.answer()
        return
    await callback.message.answer(stage_message(session), reply_markup=next_stage_keyboard())
    await callback.answer()


async def restart(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    sessions.pop(user_id, None)
    await callback.message.answer(
        "Начнём заново. С чего хотите начать?",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()


async def main() -> None:
    bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
    dp = Dispatcher()

    dp.message.register(cmd_start, CommandStart())
    dp.callback_query.register(select_path, F.data.startswith("path:"))
    dp.callback_query.register(select_cut, F.data.startswith("cut:"))
    dp.callback_query.register(select_part, F.data.startswith("part:"))
    dp.callback_query.register(select_doneness, F.data.startswith("doneness:"))
    dp.callback_query.register(next_stage, F.data == "stage:next")
    dp.callback_query.register(restart, F.data == "restart")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
