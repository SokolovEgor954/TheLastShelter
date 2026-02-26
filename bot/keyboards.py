from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
import os


load_dotenv()
ADMIN_CHAT_ID = int(os.getenv('ADMIN_CHAT_ID'))

def main_keyboard(chat_id: int, is_linked: bool = False) -> ReplyKeyboardMarkup:
    """Головне меню залежно від ролі."""
    if chat_id == ADMIN_CHAT_ID:
        return ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text='📋 Замовлення'),KeyboardButton(text='📅 Бронювання сьогодні')],
            [KeyboardButton(text='👥 Активні броні'), KeyboardButton(text='🍽 Додати страву')],
        ], resize_keyboard=True)

    if is_linked:
        return ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text='📦 Моє замовлення'), KeyboardButton(text='🪑 Моє бронювання')],
            [KeyboardButton(text='☰ Меню'),             KeyboardButton(text='❌ Скасувати бронювання')],
        ], resize_keyboard=True)

    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🔗 Прив'язати акаунт")],
    ], resize_keyboard=True)


def confirm_cancel_keyboard(res_id: int) -> InlineKeyboardMarkup:
    """Підтвердження скасування бронювання."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text='✅ Так, скасувати', callback_data=f'cancel_res:{res_id}'),
        InlineKeyboardButton(text='❌ Ні',             callback_data='cancel_no'),
    ]])


def order_status_keyboard(order_id: int, next_status: str, next_label: str) -> InlineKeyboardMarkup:
    """Кнопка зміни статусу замовлення для адміна."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=f'→ {next_label}', callback_data=f'status:{order_id}:{next_status}'),
    ]])