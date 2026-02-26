# ☢ Останній Прихисток v2.0

> Веб-додаток ресторану з постапокаліптичною термінальною естетикою.  
> Flask + PostgreSQL + Telegram Bot (aiogram)

---

## Стек технологій

| Шар | Технологія |
|-----|-----------|
| Backend | Flask, SQLAlchemy, Flask-Login, Flask-Mail |
| Database | PostgreSQL + psycopg2 |
| Bot | aiogram 3.x (asyncio) |
| Frontend | Jinja2, Bootstrap, кастомний CSS |
| Security | CSP + nonce, CSRF токени, bcrypt |
| Other | geopy, itsdangerous, python-dotenv |

---

## Структура проекту

```
FinalFlaskProject/
│
├── shared/
│   └── db.py                  # моделі БД: Users, Menu, Orders, Reservation, Table, Reviews, TelegramCode
│
├── web/
│   ├── static/
│   │   ├── css/haven.css
│   │   └── menu/              # фото страв
│   ├── templates/
│   │   ├── base.html
│   │   ├── home.html
│   │   ├── login.html
│   │   ├── register.html
│   │   ├── profile.html
│   │   ├── menu.html
│   │   ├── position.html
│   │   ├── create_order.html
│   │   ├── my_orders.html
│   │   ├── my_order.html
│   │   ├── reserved.html
│   │   ├── edit_reservation.html
│   │   ├── my_reservations.html
│   │   ├── forgot_password.html
│   │   ├── reset_password.html
│   │   └── admin/
│   │       ├── _admin_navigation.html
│   │       ├── add_position.html
│   │       ├── check_menu.html
│   │       ├── all_users.html
│   │       └── reservations_check.html
│   └── app.py                 # Flask додаток — маршрути, email функції
│
├── bot/
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── common.py          # /start, прив'язка акаунту
│   │   ├── user.py            # замовлення, бронювання, меню
│   │   └── admin.py           # адмін-панель, FSM додавання страв
│   ├── keyboards.py           # всі клавіатури
│   └── bot.py                 # запуск бота
│
├── .env                       # секретні змінні (не комітити!)
├── .gitignore
├── seed_tables.py             # одноразовий скрипт для заповнення столиків
├── run_web.py                 # запуск Flask
└── run_bot.py                 # запуск бота
```

---

## Встановлення та запуск

### 1. Клонування і залежності

```bash
git clone <repo>
cd FinalFlaskProject
python -m venv .venv
.venv\Scripts\activate       # Windows
pip install -r requirements.txt
```

### 2. Налаштування .env

Створи файл `.env` у корені проекту:

```env
SECRET_KEY=твій_секретний_ключ

PGUSER=postgres
PGPASSWORD=твій_пароль

MAIL_USERNAME=твій_gmail@gmail.com
MAIL_PASSWORD=app_password_від_google

BOT_TOKEN=токен_від_BotFather
ADMIN_CHAT_ID=твій_telegram_chat_id

ADMIN_EMAIL=твій_gmail@gmail.com
```

> **MAIL_PASSWORD** — це не пароль від Gmail, а App Password.  
> Отримати: Google Account → Безпека → Двоетапна перевірка → Паролі програм

### 3. База даних

Створи БД в PostgreSQL і запусти міграцію:

```bash
# У psql або pgAdmin:
CREATE DATABASE online_restaurant;

ALTER TABLE users ADD COLUMN IF NOT EXISTS telegram_chat_id BIGINT;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'new';
```

Запусти `shared/db.py` щоб створились всі таблиці:

```bash
python shared/db.py
```

Заповни столики:

```bash
python seed_tables.py
```

### 4. Запуск

```bash
# Сайт (термінал 1):
python run_web.py

# Бот (термінал 2):
python run_bot.py
```

Сайт доступний на `http://localhost:5000`

---

## Функціонал

### Сайт
- Реєстрація та авторизація
- Меню з пошуком і фільтрацією за назвою, інгредієнтами і ціною
- Кошик і оформлення замовлень
- Трекер статусу замовлення (Нове → Готується → Готово → Доставлено)
- Бронювання столиків з інтерактивною схемою залу
- Геолокація — бронювання тільки в межах 20 км від ресторану
- Відгуки з рейтингом на кожну страву
- Профіль зі статистикою і зміною пароля
- Скидання пароля через email (токен дійсний 30 хвилин)
- Прив'язка Telegram через 8-символьний одноразовий код
- Email-повідомлення: нове бронювання, замовлення, скасування, нові страви

### Адмін-панель (нікнейм `Admin`)
- Управління меню (активація, деактивація, видалення)
- Перегляд і скасування бронювань з фільтром по даті
- Список всіх юзерів з можливістю видалення

### Telegram бот
- Трекер статусу замовлення з сповіщеннями
- Перегляд і скасування бронювання
- Перегляд меню
- **Адмін:** управління замовленнями зі зміною статусів
- **Адмін:** перегляд бронювань (сьогодні / всі)
- **Адмін:** додавання страви через FSM діалог (6 кроків)

---

## Безпека

- **CSRF токени** — захист від підроблених форм
- **CSP + nonce** — захист від XSS атак
- **bcrypt** — хешування паролів
- **Геолокація** — обмеження зони бронювання
- **.env** — секретні дані поза кодом

---

## Адміністратор

При реєстрації створи акаунт з нікнеймом **`Admin`** — він автоматично отримає доступ до адмін-панелі.