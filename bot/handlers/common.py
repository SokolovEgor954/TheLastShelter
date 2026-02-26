from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message

from shared.db import Session, Users, TelegramCode
from bot.keyboards import main_keyboard, ADMIN_CHAT_ID
from datetime import datetime

router = Router()


def get_user_by_chat_id(chat_id: int):
    """Шукає юзера в БД по його chat_id"""
    with Session() as cursor:
        return cursor.query(Users).filter_by(telegram_chat_id=chat_id).first()



@router.message(CommandStart())
async def start(message: Message):
    chat_id = message.chat.id

    if chat_id == ADMIN_CHAT_ID:
        await message.answer(
            "☢ *Панель адміністратора — Останній Прихисток*",
            parse_mode='Markdown',
            reply_markup=main_keyboard(chat_id, is_linked=True)
        )
        return

    user = get_user_by_chat_id(chat_id)
    if user:
        await message.answer(
            f"☢ З поверненням, *{user.nickname}*!",
            parse_mode='Markdown',
            reply_markup=main_keyboard(chat_id, is_linked=True)
        )
    else:
        await message.answer(
            "☢ *Останній Прихисток*\n\nАкаунт не прив'язано.",
            parse_mode='Markdown',
            reply_markup=main_keyboard(chat_id, is_linked=False)
        )



@router.message(F.text == "🔗 Прив'язати акаунт")
async def link_account(message: Message):
    await message.answer(
        "Введіть 8-значний код з вашого профілю на сайті:\n"
        "*(Профіль → Telegram → Отримати код)*",
        parse_mode='Markdown'
    )


@router.message(F.text.len() == 8)
async def process_link_code(message: Message):
    code    = message.text.strip().upper()
    chat_id = message.chat.id

    # Не обробляти якщо вже прив'язаний
    if get_user_by_chat_id(chat_id):
        return

    with Session() as cursor:
        # Шукаємо код в таблиці телеграм-кодів
        tg_code = cursor.query(TelegramCode).filter_by(code=code).first()

        if not tg_code:
            await message.answer("❌ Невірний код. Перевірте і спробуйте ще раз.")
            return

        age = (datetime.utcnow() - tg_code.created_at).seconds
        if age > 600:
            cursor.delete(tg_code)
            cursor.commit()
            await message.answer("⏱ Код застарів. Отримайте новий на сайті.")
            return

        user = cursor.query(Users).filter_by(id=tg_code.user_id).first()
        user.telegram_chat_id = chat_id
        cursor.delete(tg_code)
        cursor.commit()

        nickname = user.nickname

    await message.answer(
        f"✅ Акаунт *{nickname}* успішно прив'язано!",
        parse_mode='Markdown',
        reply_markup=main_keyboard(chat_id, is_linked=True)
    )