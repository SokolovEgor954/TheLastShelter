from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from shared.db import Session, Users, Orders, Reservation, Menu
from sqlalchemy.orm import joinedload
from bot.keyboards import ADMIN_CHAT_ID, order_status_keyboard
from datetime import datetime, date
import os, uuid

router = Router()

STATUS_LABELS = {
    'new':       '🆕 Нове',
    'preparing': '👨‍🍳 Готується',
    'ready':     '✅ Готово',
    'delivered': '🚀 Доставлено',
}
STATUS_ORDER = ['new', 'preparing', 'ready', 'delivered']


# FSM для додавання страви
class AddDish(StatesGroup):
    name        = State()
    price       = State()
    weight      = State()
    ingredients = State()
    description = State()
    photo       = State()



def admin_only(message: Message) -> bool:
    return message.chat.id == ADMIN_CHAT_ID



@router.message(F.text == '📋 Замовлення', admin_only)
async def admin_orders(message: Message):
    with Session() as cursor:
        orders = cursor.query(Orders)\
            .options(joinedload(Orders.user))\
            .filter(Orders.status != 'delivered')\
            .order_by(Orders.order_time.desc())\
            .all()

        if not orders:
            await message.answer("Активних замовлень немає.")
            return

        for order in orders:
            items  = ', '.join(f"{n} ×{q}" for n, q in order.order_list.items())
            status = STATUS_LABELS.get(order.status, order.status)

            # Визначаємо наступний статус для кнопки
            current_idx = STATUS_ORDER.index(order.status) if order.status in STATUS_ORDER else 0
            kb = None
            if current_idx < len(STATUS_ORDER) - 1:
                next_status = STATUS_ORDER[current_idx + 1]
                next_label  = STATUS_LABELS[next_status]
                kb = order_status_keyboard(order.id, next_status, next_label)
            # kb = None якщо статус 'delivered' - кнопки не буде

            await message.answer(
                f"📦 *Замовлення #{order.id}*\n"
                f"👤 {order.user.nickname if order.user else '?'}\n"
                f"📝 {items}\n"
                f"⏰ {order.order_time.strftime('%d.%m %H:%M')}\n"
                f"Статус: *{status}*",
                parse_mode='Markdown',
                reply_markup=kb
            )


@router.callback_query(F.data.startswith('status:'))
async def change_order_status(call: CallbackQuery):
    _, order_id, new_status = call.data.split(':')

    with Session() as cursor:
        order = cursor.query(Orders)\
            .options(joinedload(Orders.user))\
            .filter_by(id=int(order_id)).first()

        if not order:
            await call.answer("Замовлення не знайдено.")
            return

        order.status = new_status
        cursor.commit()

        status_label  = STATUS_LABELS.get(new_status, new_status)
        user_chat_id  = order.user.telegram_chat_id if order.user else None
        order_items   = '\n'.join(f"  • {n} × {q}" for n, q in order.order_list.items())
        order_id_val  = order.id

    # Повідомити юзера якщо є chat_id
    if user_chat_id:
        await call.bot.send_message(user_chat_id,
            f"🔔 *Статус замовлення #{order_id_val} змінено*\n\n"
            f"{order_items}\n\n"
            f"Новий статус: *{status_label}*",
            parse_mode='Markdown')

    await call.message.edit_text(
        f"✅ Замовлення #{order_id} → *{status_label}*",
        parse_mode='Markdown'
    )




@router.message(F.text == '📅 Бронювання сьогодні', admin_only)
async def admin_today(message: Message):
    today_start = datetime.combine(date.today(), datetime.min.time())
    today_end   = datetime.combine(date.today(), datetime.max.time())

    with Session() as cursor:
        reservations = cursor.query(Reservation)\
            .options(joinedload(Reservation.user), joinedload(Reservation.table))\
            .filter(Reservation.time_start.between(today_start, today_end))\
            .order_by(Reservation.time_start)\
            .all()

        if not reservations:
            await message.answer("Сьогодні бронювань немає.")
            return

        text = f"📅 *Бронювання на сьогодні ({len(reservations)}):*\n\n"
        for r in reservations:
            text += (
                f"🪑 Столик №{r.table.number} — {r.table.label}\n"
                f"👤 {r.user.nickname if r.user else '?'}\n"
                f"⏰ {r.time_start.strftime('%H:%M')}\n\n"
            )

    await message.answer(text, parse_mode='Markdown')




@router.message(F.text == '👥 Активні броні', admin_only)
async def admin_all_reservations(message: Message):
    with Session() as cursor:
        reservations = cursor.query(Reservation)\
            .options(joinedload(Reservation.user), joinedload(Reservation.table))\
            .order_by(Reservation.time_start)\
            .all()

        if not reservations:
            await message.answer("Активних бронювань немає.")
            return

        text = f"👥 *Всі активні бронювання ({len(reservations)}):*\n\n"
        for r in reservations:
            text += (
                f"🪑 №{r.table.number} | "
                f"{r.user.nickname if r.user else '?'} | "
                f"{r.time_start.strftime('%d.%m %H:%M')}\n"
            )

    await message.answer(text, parse_mode='Markdown')




@router.message(F.text == '🍽 Додати страву', admin_only)
async def admin_add_dish(message: Message, state: FSMContext):
    await state.set_state(AddDish.name)
    await message.answer("Введіть назву страви:")


@router.message(AddDish.name)
async def add_dish_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AddDish.price)
    await message.answer("Введіть ціну (грн):")


@router.message(AddDish.price)
async def add_dish_price(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Ціна має бути числом. Спробуйте ще раз:")
        return
    await state.update_data(price=int(message.text))
    await state.set_state(AddDish.weight)
    await message.answer("Введіть вагу (г):")


@router.message(AddDish.weight)
async def add_dish_weight(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Вага має бути числом. Спробуйте ще раз:")
        return
    await state.update_data(weight=int(message.text))
    await state.set_state(AddDish.ingredients)
    await message.answer("Введіть інгредієнти (через кому):")


@router.message(AddDish.ingredients)
async def add_dish_ingredients(message: Message, state: FSMContext):
    await state.update_data(ingredients=message.text)
    await state.set_state(AddDish.description)
    await message.answer("Введіть опис:")


@router.message(AddDish.description)
async def add_dish_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(AddDish.photo)
    await message.answer("Надішліть фото страви:")


@router.message(AddDish.photo, F.photo)
async def add_dish_photo(message: Message, state: FSMContext):
    data = await state.get_data()

    file_info = await message.bot.get_file(message.photo[-1].file_id)
    downloaded = await message.bot.download_file(file_info.file_path)

    filename = f"{uuid.uuid4()}.jpg"
    filepath = os.path.join('web', 'static', 'menu', filename)

    with open(filepath, 'wb') as f:
        f.write(downloaded.read())

    with Session() as cursor:
        new_dish = Menu(
            name=data['name'],
            price=data['price'],
            weight=data['weight'],
            ingredients=data['ingredients'],
            description=data['description'],
            file_name=filename,
            active=True
        )
        cursor.add(new_dish)
        cursor.commit()

        # Email всім юзерам
        from web.app import email_new_menu_items, app
        all_emails = [u.email for u in cursor.query(Users).with_entities(Users.email).all()]
        with app.app_context():
            email_new_menu_items(all_emails, [new_dish])

    await state.clear()
    await message.answer(f"✅ Страву *{data['name']}* додано до меню!", parse_mode='Markdown')


@router.message(AddDish.photo)
async def add_dish_photo_wrong(message: Message):
    await message.answer("❌ Потрібно фото. Надішліть фото страви:")