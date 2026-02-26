from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from shared.db import Session, Users, Orders, Reservation, Menu
from sqlalchemy.orm import joinedload
from bot.keyboards import main_keyboard, confirm_cancel_keyboard, ADMIN_CHAT_ID
from web.app import email_user_cancelled_reservation, ADMIN_EMAIL, app

router = Router()

STATUS_LABELS = {
    'new':       '🆕 Нове',
    'preparing': '👨‍🍳 Готується',
    'ready':     '✅ Готово',
    'delivered': '🚀 Доставлено',
}


def get_user_by_chat_id(chat_id: int):
    """Шукає юзера в БД по його chat_id"""
    with Session() as cursor:
        return cursor.query(Users).filter_by(telegram_chat_id=chat_id).first()

# Трекер замовлення
@router.message(F.text == '📦 Моє замовлення')
async def my_order(message: Message):
    user = get_user_by_chat_id(message.chat.id)
    if not user:
        await message.answer("❌ Акаунт не прив'язано.")
        return

    with Session() as cursor:
        order = cursor.query(Orders)\
            .filter_by(user_id=user.id)\
            .order_by(Orders.order_time.desc())\
            .first()

        if not order:
            await message.answer("У вас ще немає замовлень.")
            return

        items  = '\n'.join(f"  • {name} × {qty}" for name, qty in order.order_list.items())
        status = STATUS_LABELS.get(order.status, order.status)

    await message.answer(
        f"📦 *Замовлення #{order.id}*\n\n"
        f"{items}\n\n"
        f"Статус: *{status}*\n"
        f"Час: {order.order_time.strftime('%d.%m.%Y %H:%M')}",
        parse_mode='Markdown'
    )


@router.message(F.text == '🪑 Моє бронювання')
async def my_reservation(message: Message):
    user = get_user_by_chat_id(message.chat.id)
    if not user:
        await message.answer("❌ Акаунт не прив'язано.")
        return

    with Session() as cursor:
        res = cursor.query(Reservation)\
            .options(joinedload(Reservation.table))\
            .filter_by(user_id=user.id)\
            .first()

        if not res:
            await message.answer("У вас немає активних бронювань.")
            return

        text = (
            f"🪑 *Ваше бронювання*\n\n"
            f"Столик №{res.table.number} — {res.table.label}\n"
            f"Тип: {res.table.type_table} ос.\n"
            f"Час: {res.time_start.strftime('%d.%m.%Y %H:%M')}"
        )
        res_id     = res.id
        table_num  = res.table.number
        time_start = res.time_start.strftime('%d.%m %H:%M')

    await message.answer(text, parse_mode='Markdown')


@router.message(F.text == '❌ Скасувати бронювання')
async def cancel_reservation(message: Message):
    user = get_user_by_chat_id(message.chat.id)
    if not user:
        await message.answer("❌ Акаунт не прив'язано.")
        return

    with Session() as cursor:
        res = cursor.query(Reservation)\
            .options(joinedload(Reservation.table))\
            .filter_by(user_id=user.id)\
            .first()

        if not res:
            await message.answer("У вас немає активних бронювань.")
            return

        res_id     = res.id
        table_num  = res.table.number
        time_start = res.time_start.strftime('%d.%m %H:%M')

    await message.answer(
        f"Скасувати бронювання столику №{table_num} на {time_start}?",
        reply_markup=confirm_cancel_keyboard(res_id)
    )


@router.callback_query(F.data.startswith('cancel_res:'))
async def confirm_cancel(call: CallbackQuery):
    res_id = int(call.data.split(':')[1])

    with Session() as cursor:
        res = cursor.query(Reservation)\
            .options(joinedload(Reservation.table), joinedload(Reservation.user))\
            .filter_by(id=res_id).first()
        if res:
            table_number = res.table.number
            table_label = res.table.label
            time_start = res.time_start.strftime('%d.%m.%Y %H:%M')
            user_nickname = res.user.nickname
            user_email = res.user.email

            cursor.delete(res)
            cursor.commit()

    with app.app_context():
        email_user_cancelled_reservation(
            admin_email=ADMIN_EMAIL,
            user_nickname=user_nickname,
            user_email=user_email,
            table_number=table_number,
            table_label=table_label,
            time_start=time_start
        )

    await call.message.edit_text("✅ Бронювання скасовано.")


@router.callback_query(F.data == 'cancel_no')
async def cancel_no(call: CallbackQuery):
    await call.message.edit_text("Скасування відхилено.")


@router.message(F.text == '☰ Меню')
async def show_menu(message: Message):
    with Session() as cursor:
        positions = cursor.query(Menu).filter_by(active=True).all()

        if not positions:
            await message.answer("Меню порожнє.")
            return

        text = "🍽 *Меню Останнього Прихистку:*\n\n"
        for p in positions:
            text += f"• *{p.name}* — {p.price} ₴ ({p.weight} г)\n"

    await message.answer(text, parse_mode='Markdown')