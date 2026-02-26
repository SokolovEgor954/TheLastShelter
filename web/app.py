from flask import Flask, render_template, request, redirect, url_for, flash, session, g
from flask_login import login_required, current_user, login_user, logout_user
from shared.db import Session, Users, Menu, Orders, Reservation, Table, Reviews, TelegramCode
from flask_login import LoginManager
from datetime import datetime
import os
import uuid
import secrets
from geopy.distance import geodesic
from sqlalchemy.orm import joinedload
from sqlalchemy import func
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
import random, string
from dotenv import load_dotenv
import os


load_dotenv()


app = Flask(__name__,
            static_folder='static',
            template_folder='templates')

FILES_PATH = 'web/static/menu'

app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['MAX_FORM_MEMORY_SIZE'] = 1024 * 1024
app.config['MAX_FORM_PARTS'] = 500
app.config['SESSION_COOKIE_SAMESITE'] = 'Strict'
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')


login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    with Session() as session:
        user = session.query(Users).filter_by(id = user_id).first()
        if user:
            return user


RESTAURANT_COORDS = (50.4501, 30.5234)
BOOKING_RADIUS_KM = 20
TABLE_NUM = {
    '1-2': 10,
    '3-4': 8,
    '4+': 4

}

# Конфігурація email
app.config['MAIL_SERVER']   = 'smtp.gmail.com'
app.config['MAIL_PORT']     = 587
app.config['MAIL_USE_TLS']  = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = ('Останній Прихисток', os.getenv('MAIL_USERNAME'))

mail = Mail(app)

ADMIN_EMAIL = os.getenv('ADMIN_EMAIL')

# Серіалізатор - для підписання токенів при скиданні паролю
SERIALIZER  = URLSafeTimedSerializer(app.config['SECRET_KEY'])


# Email-функції
def send_email(to, subject, body_html):
    """Базова функція відправки."""
    try:
        msg = Message(subject=subject, recipients=[to], html=body_html)
        mail.send(msg)
        return True
    except Exception as e:
        print(f"[MAIL ERROR] {e}")
        return False


def email_new_reservation(admin_email, user_nickname, user_email, table_number, table_label, time_start):
    """Адміну - повідомлення про нове бронювання."""
    send_email(admin_email,
        subject="☢ Нове бронювання | Останній Прихисток",
        body_html=f"""
        <div style="font-family:monospace; background:#0a0f0a; color:#4cff80; padding:24px; border:1px solid #4cff80;">
            <h2 style="color:#4cff80;">☢ НОВЕ БРОНЮВАННЯ</h2>
            <p><b>Користувач:</b> {user_nickname} ({user_email})</p>
            <p><b>Столик №{table_number}</b> — {table_label}</p>
            <p><b>Час:</b> {time_start}</p>
            <hr style="border-color:#4cff80; opacity:0.3;">
            <p style="opacity:0.6; font-size:12px;">Останній Прихисток — Система бронювань</p>
        </div>
        """)

def email_edit_reservation(admin_email, user_nickname, user_email, old_table_number, old_table_label, old_time_start,
                          new_table_number, new_table_label, new_time_start):
    """Адміну - оновлення бронювання."""
    send_email(admin_email,
        subject="☢ Оновлення бронювання | Останній Прихисток",
        body_html=f"""
        <div style="font-family:monospace; background:#0a0f0a; color:#4cff80; padding:24px; border:1px solid #4cff80; line-height:1.4;">
    <h2 style="color:#4cff80; margin-top:0;">🔄 ОНОВЛЕННЯ БРОНЮВАННЯ</h2>
    <p><b>Користувач:</b> {user_nickname} ({user_email})</p>
    
    <div style="display: flex; gap: 20px; margin-top: 20px;">
        <div style="flex: 1; border: 1px dashed #4cff80; padding: 12px; opacity: 0.6;">
            <p style="text-align: center; margin-top: 0;"><b>[ СТАРІ ДАНІ ]</b></p>
            <hr style="border-color:#4cff80; opacity:0.3;">
            <p>Столик №{old_table_number}</p>
            <p>Зона: {old_table_label}</p>
            <p>Час: {old_time_start}</p>
        </div>

        <div style="flex: 1; border: 2px solid #4cff80; padding: 12px; background: rgba(76, 255, 128, 0.05);">
            <p style="text-align: center; margin-top: 0;"><b>[ НОВІ ДАНІ ]</b></p>
            <hr style="border-color:#4cff80; opacity:0.6;">
            <p>Столик №{new_table_number}</p>
            <p>Зона: {new_table_label}</p>
            <p>Час: {new_time_start}</p>
        </div>
    </div>

    <p style="margin-top: 20px; font-weight: bold; text-align: center; color: #000; background: #4cff80;">СТАТУС: УСПІШНО МОДИФІКОВАНО</p>
    
    <hr style="border-color:#4cff80; opacity:0.3; margin-top: 20px;">
    <p style="opacity:0.6; font-size:12px; margin-bottom: 0;">Останній Прихисток — Система бронювань v2.0.4</p>
</div>
        """)

def email_order_confirmed(user_email, user_nickname, order_id, order_list, total_price):
    """Юзеру - замовлення прийняти."""
    items_html = ''.join(
        f"<tr><td style='padding:4px 12px;'>{name}</td><td style='padding:4px 12px;'>× {qty}</td></tr>"
        for name, qty in order_list.items()
    )
    send_email(user_email,
        subject=f"✅ Замовлення #{order_id} прийнято | Останній Прихисток",
        body_html=f"""
        <div style="font-family:monospace; background:#0a0f0a; color:#4cff80; padding:24px; border:1px solid #4cff80;">
            <h2 style="color:#4cff80;">✅ ЗАМОВЛЕННЯ ПРИЙНЯТО</h2>
            <p>Вітаємо, <b>{user_nickname}</b>!</p>
            <p>Ваше замовлення <b>#{order_id}</b> успішно оформлено.</p>
            <table style="border-collapse:collapse; margin:12px 0;">
                <tr style="opacity:0.6;"><th style="padding:4px 12px; text-align:left;">Страва</th><th style="padding:4px 12px;">К-сть</th></tr>
                {items_html}
            </table>
            <p><b>Загальна сума: {total_price} ₴</b></p>
            <hr style="border-color:#4cff80; opacity:0.3;">
            <p style="opacity:0.6; font-size:12px;">Останній Прихисток — Кухня працює</p>
        </div>
        """)


def email_reservation_cancelled(user_email, user_nickname, table_number, table_label, time_start):
    """Юзеру - бронювання скасовано адміном."""
    send_email(user_email,
        subject="⚠ Бронювання скасовано | Останній Прихисток",
        body_html=f"""
        <div style="font-family:monospace; background:#0a0f0a; color:#4cff80; padding:24px; border:1px solid #ff5050;">
            <h2 style="color:#ff5050;">⚠ БРОНЮВАННЯ СКАСОВАНО</h2>
            <p>Вітаємо, <b>{user_nickname}</b>.</p>
            <p>На жаль, ваше бронювання було скасовано адміністратором.</p>
            <p><b>Столик №{table_number}</b> — {table_label}</p>
            <p><b>Час:</b> {time_start}</p>
            <p>Ви можете забронювати інший столик на нашому сайті.</p>
            <hr style="border-color:#ff5050; opacity:0.3;">
            <p style="opacity:0.6; font-size:12px;">Останній Прихисток</p>
        </div>
        """)


def email_user_cancelled_reservation(admin_email, user_nickname, user_email, table_number, table_label, time_start):
    """Адміну - юзер сам скасував бронювання."""
    send_email(admin_email,
        subject="⚠ Бронювання скасовано юзером | Останній Прихисток",
        body_html=f"""
        <div style="font-family:monospace; background:#0a0f0a; color:#4cff80; padding:24px; border:1px solid #ffc800;">
            <h2 style="color:#ffc800;">⚠ БРОНЮВАННЯ СКАСОВАНО ЮЗЕРОМ</h2>
            <p><b>Користувач:</b> {user_nickname} ({user_email})</p>
            <p><b>Столик №{table_number}</b> — {table_label}</p>
            <p><b>Час був:</b> {time_start}</p>
            <hr style="border-color:#ffc800; opacity:0.3;">
            <p style="opacity:0.6; font-size:12px;">Останній Прихисток — Система бронювань</p>
        </div>
        """)


def email_new_menu_items(all_users_emails, new_items):
    """Всім юзерам - нові страви в меню."""
    items_html = ''.join(
        f"<li style='margin:6px 0;'><b>{item.name}</b> — {item.price} ₴</li>"
        for item in new_items
    )
    for email in all_users_emails:
        send_email(email,
            subject="🍽 Нові страви в меню | Останній Прихисток",
            body_html=f"""
            <div style="font-family:monospace; background:#0a0f0a; color:#4cff80; padding:24px; border:1px solid #4cff80;">
                <h2 style="color:#4cff80;">🍽 НОВІ СТРАВИ В МЕНЮ</h2>
                <p>Прихисток поповнив запаси! Нові позиції:</p>
                <ul style="padding-left:20px;">{items_html}</ul>
                <a href="http://localhost:5000/menu"
                   style="display:inline-block; margin-top:12px; padding:10px 20px;
                          background:#4cff80; color:#000; text-decoration:none; font-weight:bold;">
                    ☰ Переглянути меню
                </a>
                <hr style="border-color:#4cff80; opacity:0.3; margin-top:16px;">
                <p style="opacity:0.6; font-size:12px;">Останній Прихисток</p>
            </div>
            """)


def email_reset_password(user_email, reset_url):
    """Юзеру - скидання пароля."""
    send_email(user_email,
        subject="🔑 Скидання пароля | Останній Прихисток",
        body_html=f"""
        <div style="font-family:monospace; background:#0a0f0a; color:#4cff80; padding:24px; border:1px solid #4cff80;">
            <h2 style="color:#4cff80;">🔑 СКИДАННЯ ПАРОЛЯ</h2>
            <p>Ви запросили скидання пароля для вашого акаунту.</p>
            <p>Посилання дійсне протягом <b>30 хвилин</b>.</p>
            <a href="{reset_url}"
               style="display:inline-block; margin-top:12px; padding:10px 20px;
                      background:#4cff80; color:#000; text-decoration:none; font-weight:bold;">
                🔑 Скинути пароль
            </a>
            <p style="margin-top:12px; opacity:0.6;">Якщо ви не запитували скидання — проігноруйте цей лист.</p>
            <hr style="border-color:#4cff80; opacity:0.3;">
            <p style="opacity:0.6; font-size:12px;">Останній Прихисток</p>
        </div>
        """)



# Безпека
@app.before_request
def generate_nonce():
    """Генерує nonce перед кожним запитом і зберігає його в 'g'."""
    g.nonce = secrets.token_urlsafe(16)


@app.after_request
def apply_csp(response):
    """Додає CSP заголовок до відповіді"""
    if hasattr(g, 'nonce'):
        csp = (
            f"default-src 'self'; "
            f"script-src 'self' 'nonce-{g.nonce}' https://cdn.jsdelivr.net; "
            f"style-src 'self' https://fonts.googleapis.com https://cdn.jsdelivr.net 'unsafe-inline'; "
            f"font-src 'self' https://fonts.gstatic.com; "
            f"img-src 'self' data:; "
            f"connect-src 'self' https://cdn.jsdelivr.net; "
            f"form-action 'self'; "
            f"frame-ancestors 'none'; "
            f"base-uri 'self'; "
        )
        response.headers["Content-Security-Policy"] = csp

    return response



# Базові маршрути
@app.route('/')
@app.route('/home')
def home():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(16)
    return render_template('home.html', nonce=g.nonce)


@app.route("/register", methods = ['GET','POST'])
def register():
    if request.method == 'POST':
        if request.form.get("csrf_token") != session["csrf_token"]:
            return "Запит заблоковано!", 403
        nickname = request.form['nickname']
        email = request.form['email']
        password = request.form['password']

        if len(password) < 8:
            flash('Пароль повинен бути не менше 8 символів!', 'danger')
            return render_template('register.html', csrf_token=session["csrf_token"])

        with Session() as cursor:
            if cursor.query(Users).filter_by(email=email).first() or cursor.query(Users).filter_by(nickname = nickname).first():
                flash('Користувач з таким email або нікнеймом вже існує!', 'danger')
                return render_template('register.html',csrf_token=session["csrf_token"])

            new_user = Users(nickname=nickname, email=email)
            new_user.set_password(password)
            cursor.add(new_user)
            cursor.commit()
            cursor.refresh(new_user)
            login_user(new_user)
            return redirect(url_for('home'))
    return render_template('register.html',csrf_token=session["csrf_token"])


@app.route("/login", methods = ["GET","POST"])
def login():
    if request.method == 'POST':
        if request.form.get("csrf_token") != session["csrf_token"]:
            return "Запит заблоковано!", 403

        nickname = request.form['nickname']
        password = request.form['password']

        with Session() as cursor:
            user = cursor.query(Users).filter_by(nickname = nickname).first()
            if user and user.check_password(password):
                login_user(user)
                return redirect(url_for('home'))

            flash('Неправильний nickname або пароль!', 'danger')

    return render_template('login.html', csrf_token=session["csrf_token"])


@app.route("/logout", methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    session.pop('_flashes', None)
    return redirect(url_for('login'))



# Профіль
@app.route('/profile')
@login_required
def profile():
    with Session() as cursor:
        # Статистика для профілю
        orders_count = cursor.query(Orders).filter_by(user_id=current_user.id).count()
        reserv_count = cursor.query(Reservation).filter_by(user_id=current_user.id).count()

    return render_template('profile.html',
                           user=current_user,
                           orders_count=orders_count,
                           reserv_count=reserv_count,
                           csrf_token=session['csrf_token'])


@app.route('/profile/change_password', methods=['POST'])
@login_required
def change_password():
    if request.form.get("csrf_token") != session["csrf_token"]:
        return "Запит заблоковано!", 403

    old_password = request.form['old_password']
    new_password = request.form['new_password']
    confirm_password = request.form['confirm_password']

    if new_password != confirm_password:
        flash('Паролі не збігаються!', 'danger')
        return redirect(url_for('profile'))

    if len(new_password) < 8:
        flash('Новий пароль повинен бути не менше 8 символів!', 'danger')
        return redirect(url_for('profile'))

    with Session() as cursor:
        user = cursor.query(Users).filter_by(id=current_user.id).first()
        if not user.check_password(old_password):
            flash('Невірний поточний пароль!', 'danger')
            return redirect(url_for('profile'))

        user.set_password(new_password)
        cursor.commit()

    flash('Пароль успішно змінено!', 'success')
    return redirect(url_for('profile'))



# Меню
@app.route('/menu')
def menu():
    with Session() as db:
        all_positions = db.query(Menu).filter_by(active=True).all()
    return render_template('menu.html',
                           all_positions=all_positions,
                           csrf_token=session.get('csrf_token', ''),
                           nonce=g.nonce)


@app.route("/add_position", methods=['GET', 'POST'])
@login_required
def add_position():
    if current_user.nickname != 'Admin':
        return redirect(url_for('home'))

    if request.method == "POST":
        if request.form.get("csrf_token") != session["csrf_token"]:
            return "Запит заблоковано!", 403

        name = request.form['name']
        file = request.files.get('img')
        ingredients = request.form['ingredients']
        description = request.form['description']
        price = request.form['price']
        weight = request.form['weight']

        if not file or not file.filename:
            flash('Файл не вибрано або завантаження не вдалося', 'danger')
            return redirect(request.url)

        unique_filename = f"{uuid.uuid4()}_{file.filename}"

        upload_folder = os.path.join(app.root_path, 'static', 'menu')

        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)

        output_path = os.path.join(upload_folder, unique_filename)

        file.save(output_path)

        with Session() as cursor:
            new_position = Menu(
                name=name,
                ingredients=ingredients,
                description=description,
                price=price,
                weight=weight,
                file_name=unique_filename  # Зберігаємо тільки ім'я файлу, а не шлях
            )
            cursor.add(new_position)
            cursor.commit()
            cursor.refresh(new_position)

            # Розсилка про нову страву
            all_emails = [u.email for u in cursor.query(Users).with_entities(Users.email).all()]
            email_new_menu_items(all_emails, [new_position])

        flash('Позицію додано успішно!', 'success')
        return redirect(url_for('menu'))

    return render_template('admin/add_position.html', csrf_token=session["csrf_token"])

@app.route('/position/<int:menu_id>', methods=['GET', 'POST'])
def position(menu_id):
    if request.method == 'POST':
        if request.form.get("csrf_token") != session["csrf_token"]:
            return "Запит заблоковано!", 403

        position_name = request.form.get('name')
        position_num  = request.form.get('num')

        basket = session.get('basket', {})
        basket[position_name] = position_num
        session['basket'] = basket

        flash('Позицію додано у кошик!')

        # Поветраємо юзера на сторінку на якій він був до цього
        next_page = request.form.get('next')
        if next_page == 'menu':
            return redirect(url_for('menu'))
        return redirect(url_for('position', menu_id=menu_id))


    with Session() as cursor:
        us_position = cursor.query(Menu).filter_by(active=True, id=menu_id).first()

        if not us_position:
            flash('Позицію не знайдено', 'danger')
            return redirect(url_for('menu'))

        # joinedload() - підтягує усі дані юзера з відгуком одним разом
        reviews_raw = cursor.query(Reviews)\
            .options(joinedload(Reviews.user))\
            .filter_by(menu_id=menu_id)\
            .order_by(Reviews.created_at.desc())\
            .all()

        reviews = [
            {
                "id":         r.id,
                "rating":     r.rating,
                "comment":    r.comment,
                "author":     r.user.nickname if r.user else '?',
                "created_at": r.created_at.strftime('%d.%m.%Y') if r.created_at else '',
                "user_id": r.user_id
            }
            for r in reviews_raw
        ]

        # Середній рейтинг
        avg = cursor.query(func.avg(Reviews.rating)).filter_by(menu_id=menu_id).scalar()
        avg_rating = round(float(avg), 1) if avg else None

        # Чи залишав юзер відгук до цього
        user_reviewed = False
        if current_user.is_authenticated:
            user_reviewed = bool(
                cursor.query(Reviews).filter_by(
                    menu_id=menu_id, user_id=current_user.id
                ).first()
            )

    return render_template('position.html',
                           csrf_token=session["csrf_token"],
                           position=us_position,
                           reviews=reviews,
                           avg_rating=avg_rating,
                           user_reviewed=user_reviewed,
                           nonce=g.nonce)



# Відгуки
@app.route('/review/add/<int:menu_id>', methods=['POST'])
@login_required
def add_review(menu_id):
    if request.form.get("csrf_token") != session["csrf_token"]:
        return "Запит заблоковано!", 403

    rating  = request.form.get('rating', type=int)
    comment = request.form.get('comment', '').strip()

    if not rating or not 1 <= rating <= 5:
        flash('Оберіть оцінку від 1 до 5', 'danger')
        return redirect(url_for('position', menu_id=menu_id))

    with Session() as cursor:
        existing = cursor.query(Reviews).filter_by(
            menu_id=menu_id, user_id=current_user.id
        ).first()

        if existing:
            flash('Ви вже залишали відгук на цю страву', 'warning')
        else:
            cursor.add(Reviews(
                user_id=current_user.id,
                menu_id=menu_id,
                rating=rating,
                comment=comment if comment else None,
            ))
            cursor.commit()
            flash('Дякуємо за відгук!', 'success')

    return redirect(url_for('position', menu_id=menu_id))

@app.route('/review/delete/<int:review_id>', methods=['POST'])
@login_required
def delete_review(review_id):
    if request.form.get("csrf_token") != session["csrf_token"]:
        return "Запит заблоковано!", 403

    menu_id = request.form.get('menu_id', type=int)

    with Session() as cursor:
        review = cursor.query(Reviews).filter_by(id=review_id).first()

        if not review:
            flash('Відгук не знайдено', 'danger')
            return redirect(url_for('position', menu_id=menu_id))

        # Видаляти може автор або адмін
        if review.user_id != current_user.id and current_user.nickname != 'Admin':
            flash('Немає прав для видалення', 'danger')
            return redirect(url_for('position', menu_id=menu_id))

        cursor.delete(review)
        cursor.commit()
        flash('Відгук видалено', 'success')

    return redirect(url_for('position', menu_id=menu_id))



# Замовлення
@app.route('/create_order', methods=['GET','POST'])
def create_order():
    basket = session.get('basket', {})

    with Session() as cursor:
        # Рахуємо суму замовлення
        total_price = 0
        for name, qty in basket.items():
            pos = cursor.query(Menu).filter_by(name=name).first()
            if pos:
                total_price += pos.price * int(qty)

        if request.method == 'POST':
            if request.form.get("csrf_token") != session["csrf_token"]:
                return "Запит заблоковано!", 403

            if not current_user.is_authenticated:
                flash("Для оформлення замовлення необхідно увійти в акаунт")
                return redirect(url_for('login'))

            if not basket:
                flash("Кошик порожній")
                return redirect(url_for('create_order'))

            new_order = Orders(
                order_list=basket,
                order_time=datetime.now(),
                user_id=current_user.id
            )
            cursor.add(new_order)
            cursor.commit()

            email_order_confirmed(
                user_email=current_user.email,
                user_nickname=current_user.nickname,
                order_id=new_order.id,
                order_list=basket,
                total_price=total_price
            )
            session.pop('basket', None)
            flash('Замовлення успішно оформлено!')
            return redirect(url_for('my_orders'))

        # Передаємо позиції щоб шаблон показав деталі
        positions = cursor.query(Menu).filter(Menu.name.in_(basket.keys())).all() if basket else []

    return render_template('create_order.html',
                           basket=basket,
                           total_price=total_price,
                           positions=positions,
                           csrf_token=session['csrf_token'])


@app.route('/my_orders')
@login_required
def my_orders():
    with Session() as cursor:
        us_orders = cursor.query(Orders).filter_by(user_id = current_user.id).all()
    return render_template('my_orders.html', us_orders = us_orders)


@app.route('/my_order/<int:id>')
@login_required
def my_order(id):
    with Session() as cursor:
        us_order = cursor.query(Orders).filter_by(id = id).first()

        if not us_order or (us_order.user_id != current_user.id and current_user.nickname != 'Admin'):
            flash('Замовлення не знайдено або у вас немає доступу.', 'danger')
            return redirect(url_for('my_orders'))

        total_price = sum(int(cursor.query(Menu).filter_by(name=i).first().price) * int(cnt) for i, cnt in us_order.order_list.items())

        return render_template('my_order.html', order=us_order, total_price=total_price)


@app.route('/cancel_order/<int:id>', methods=['POST'])
@login_required
def cancel_order(id):
    if request.form.get('csrf_token') != session['csrf_token']:
        return 'Запит заблоковано!', 403

    with Session() as cursor:
        order = cursor.query(Orders).filter_by(id=id, user_id=current_user.id).first()

        if order:
            cursor.delete(order)
            cursor.commit()
            flash('Замовлення скасовано', 'success')
        else:
            flash('Не вдалося знайти замовлення або у вас немає прав', 'danger')

    return redirect(url_for('my_orders'))



# Бронювання
@app.route('/reserved', methods=['GET', 'POST'])
@login_required
def reserved():
    message = None

    if request.method == "POST":
        if request.form.get("csrf_token") != session["csrf_token"]:
            return "Запит заблоковано!", 403

        table_id   = request.form.get('table_id')
        time_start = request.form.get('time')
        user_lat   = request.form.get('latitude')
        user_lon   = request.form.get('longitude')

        if not user_lat or not user_lon:
            message = 'Дозвольте доступ до геолокації.'
        else:
            distance = geodesic(RESTAURANT_COORDS, (float(user_lat), float(user_lon))).km
            if distance > BOOKING_RADIUS_KM:
                message = f"Ви за межами зони бронювання ({distance:.1f} км від нас)."
            else:
                with Session() as cursor:
                    existing = cursor.query(Reservation).filter_by(user_id=current_user.id).first()
                    if existing:
                        message = 'У вас вже є активна бронь. Скасуйте її щоб створити нову.'
                    else:
                        table_taken = cursor.query(Reservation).filter_by(table_id=table_id).first()
                        if table_taken:
                            message = 'Цей столик вже заброньований. Оберіть інший.'
                        else:
                            new_res = Reservation(table_id=table_id, time_start=time_start, user_id=current_user.id)
                            cursor.add(new_res)
                            cursor.commit()

                            # Отримуємо дані столика поки сесія відкрита
                            table = cursor.query(Table).filter_by(id=table_id).first()
                            email_new_reservation(
                                admin_email=ADMIN_EMAIL,
                                user_nickname=current_user.nickname,
                                user_email=current_user.email,
                                table_number=table.number,
                                table_label=table.label,
                                time_start=time_start
                            )
                            message = f'✅ Столик №{table.number} ({table.label}) успішно заброньовано!'

    with Session() as cursor:
        all_tables = cursor.query(Table).all()
        reserved_ids = {r.table_id for r in cursor.query(Reservation).all()}

    # Перетворюємо об'єкти на словники для передачі
    tables_json = [
        {"id": t.id, "number": t.number, "type": t.type_table,
         "label": t.label, "x": t.x, "y": t.y, "taken": t.id in reserved_ids}
        for t in all_tables
    ]

    return render_template('reserved.html',
                           tables=tables_json,
                           message=message,
                           csrf_token=session["csrf_token"],
                           nonce=g.nonce,
                           now=datetime.now().strftime('%Y-%m-%dT%H:%M'))

@app.route('/my_reservations')
@login_required
def my_reservations():
    with Session() as cursor:
        #.options(joinedload(Reservation.table)) - потрібно для того щоб уникнути "лінивої загрузки" і у нас підгрузило інфу про столи
        reservations_raw = cursor.query(Reservation)\
            .options(joinedload(Reservation.table))\
            .filter_by(user_id=current_user.id)\
            .order_by(Reservation.time_start.desc())\
            .all()

        # Витягуємо всі дані поки сесія відкрита
        reservations = [
            {
                "id": r.id,
                "time_start": r.time_start,
                "table_number": r.table.number if r.table else '?',
                "table_label": r.table.label if r.table else '?',
                "table_type": r.table.type_table if r.table else '?',
            }
            for r in reservations_raw
        ]

    return render_template("my_reservations.html", reservations=reservations,
                           csrf_token=session['csrf_token'])


@app.route('/reservation/cancel/<int:res_id>', methods=['POST'])
@login_required
def cancel_reservation(res_id):
    if request.form.get("csrf_token") != session["csrf_token"]:
        return "Запит заблоковано!", 403

    with Session() as cursor:
        res = cursor.query(Reservation)\
            .options(joinedload(Reservation.table))\
            .filter_by(id=res_id, user_id=current_user.id)\
            .first()

        if not res:
            flash('Бронювання не знайдено.', 'danger')
            return redirect(url_for('my_reservations'))

        table_number = res.table.number
        table_label  = res.table.label
        time_start   = res.time_start.strftime('%d.%m.%Y %H:%M')

        cursor.delete(res)
        cursor.commit()

    email_user_cancelled_reservation(
        admin_email=ADMIN_EMAIL,
        user_nickname=current_user.nickname,
        user_email=current_user.email,
        table_number=table_number,
        table_label=table_label,
        time_start=time_start
    )

    flash('Бронювання скасовано.', 'success')
    return redirect(url_for('my_reservations'))


@app.route('/edit_reservation/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_reservation(id):

    with Session() as cursor:
        reserv = cursor.query(Reservation)\
            .options(joinedload(Reservation.table))\
            .filter_by(id=id, user_id=current_user.id)\
            .first()

        if not reserv:
            flash("Бронювання не знайдено", "danger")
            return redirect(url_for("my_reservations"))

        if request.method == "POST":
            if request.form.get("csrf_token") != session["csrf_token"]:
                return "Запит заблоковано!", 403

            new_time_str     = request.form["time"]
            new_table_id = request.form["table_id"]

            new_time_dt = datetime.strptime(new_time_str, '%Y-%m-%dT%H:%M')

            # Зберігаємо старі дані для листа адміну
            old_table_number = reserv.table.number
            old_table_label = reserv.table.label
            old_time_start = reserv.time_start

            # Якщо столик змінився - перевіряємо що новий не зайнятий
            if str(reserv.table_id) != str(new_table_id):
                taken = cursor.query(Reservation).filter(
                    Reservation.table_id == new_table_id,
                    Reservation.id != id # поточний не рахуємо
                ).first()
                if taken:
                    flash("Цей столик вже заброньований. Оберіть інший.", "danger")
                    return redirect(url_for("edit_reservation", id=id))

            reserv.time_start = new_time_dt
            reserv.table_id   = int(new_table_id)
            cursor.commit()

            new_table = cursor.query(Table).filter_by(id=int(new_table_id)).first()

            email_edit_reservation(
                admin_email=ADMIN_EMAIL,
                user_nickname=current_user.nickname,
                user_email=current_user.email,
                old_table_number=old_table_number,
                old_table_label=old_table_label,
                old_time_start=old_time_start.strftime('%d.%m.%Y %H:%M'),  # ← strftime тут
                new_table_number=new_table.number,
                new_table_label=new_table.label,
                new_time_start=new_time_dt.strftime('%d.%m.%Y %H:%M')  # ← і тут
            )

            flash("Бронювання змінено!", "success")
            return redirect(url_for("profile"))

        # GET - витягуємо всі дані поки сесія відкрита
        table_number = reserv.table.number if reserv.table else '?'
        table_id_cur = reserv.table_id
        reserv_id    = reserv.id
        time_val     = reserv.time_start.strftime('%Y-%m-%dT%H:%M') if reserv.time_start else ''

        all_tables   = cursor.query(Table).all()
        reserved_ids = {
            r.table_id for r in cursor.query(Reservation).all()
            if r.id != id  # не рахуємо поточне бронювання як зайняте
        }

        # Передаємо JSON для JS карти столиків
        tables_json = [
            {
                "id": t.id,
                "number": t.number,
                "type": t.type_table,
                "label": t.label,
                "x": t.x,
                "y": t.y,
                "taken": t.id in reserved_ids,
                "current": t.id == table_id_cur,
            }
            for t in all_tables
        ]

    return render_template("edit_reservation.html",
                           reserv_id=reserv_id,
                           table_id_cur=table_id_cur,
                           table_number=table_number,
                           time_val=time_val,
                           tables=tables_json,
                           csrf_token=session["csrf_token"],
                           nonce=g.nonce,
                           now=datetime.now().strftime('%Y-%m-%dT%H:%M'))



#Адмін-панель
@app.route('/reservations_check', methods=['GET', 'POST'])
@login_required
def reservations_check():
    if current_user.nickname != 'Admin':
        return redirect(url_for('home'))

    if request.method == 'POST':
        reserv_id = request.form.get('reserv_id')
        with Session() as cursor:
            res = cursor.query(Reservation) \
                .options(joinedload(Reservation.user), joinedload(Reservation.table)) \
                .filter_by(id=reserv_id).first()

            if res:
                email_reservation_cancelled(
                    user_email=res.user.email,
                    user_nickname=res.user.nickname,
                    table_number=res.table.number,
                    table_label=res.table.label,
                    time_start=res.time_start.strftime('%d.%m.%Y %H:%M')
                )
                cursor.delete(res)
                cursor.commit()

    selected_date = request.args.get("date")
    with Session() as cursor:
        query = cursor.query(Reservation)\
            .options(joinedload(Reservation.table), joinedload(Reservation.user))

        # Фільтр по даті
        if selected_date:
            try:
                date_obj = datetime.strptime(selected_date, "%Y-%m-%d")
                next_day = date_obj.replace(hour=23, minute=59)
                query = query.filter(
                    Reservation.time_start.between(date_obj, next_day)
                )
            except:
                pass

        raw = query.order_by(Reservation.time_start.desc()).all()

        all_reservations = [
            {
                "id":            r.id,
                "time_start":    r.time_start,
                "user_nickname": r.user.nickname if r.user else '?',
                "table_number":  r.table.number if r.table else '?',
                "table_label":   r.table.label if r.table else '?',
                "table_type":    r.table.type_table if r.table else '?',
            }
            for r in raw
        ]

    return render_template(
        'admin/reservations_check.html',
        all_reservations=all_reservations,
        selected_date=selected_date,
        csrf_token=session['csrf_token'],
        nonce=g.nonce
    )


@app.route('/menu_check', methods=['GET', 'POST'])
@login_required
def menu_check():
    if current_user.nickname != 'Admin':
        return redirect(url_for('home'))

    if request.method == "POST":
        if request.form.get("csrf_token") != session["csrf_token"]:
            return "Запит заблоковано!", 403

        position_id = request.form['pos_id']
        with Session() as cursor:
            position_obj = cursor.query(Menu).filter_by(id=position_id).first()

            if 'change_status' in request.form:
                position_obj.active = not position_obj.active
            elif 'delete_position' in request.form:
                cursor.delete(position_obj)
            cursor.commit()

    with Session() as cursor:
        all_positions = cursor.query(Menu).all()
    return render_template('admin/check_menu.html',
                           all_positions=all_positions,
                           csrf_token=session["csrf_token"],
                           nonce=g.nonce)


@app.route('/all_users')
@login_required
def all_users():
    if current_user.nickname != 'Admin':
        return redirect(url_for('home'))

    with Session() as cursor:
        all_users = cursor.query(Users).with_entities(Users.id, Users.nickname, Users.email).all()

    return render_template('admin/all_users.html',
                            all_users=all_users,
                            csrf_token=session['csrf_token'],
                            nonce=g.nonce)

@app.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if current_user.nickname != 'Admin':
        return redirect(url_for('home'))

    if request.form.get("csrf_token") != session["csrf_token"]:
        return "Запит заблоковано!", 403

    with Session() as cursor:
        user = cursor.query(Users).filter_by(id=user_id).first()

        if not user:
            flash('Користувача не знайдено', 'danger')
            return redirect(url_for('all_users'))

        if user.nickname == 'Admin':
            flash('Не можна видалити адміністратора!', 'danger')
            return redirect(url_for('all_users'))

        # Чистимо всі записи
        cursor.query(Orders).filter_by(user_id=user_id).delete()
        cursor.query(Reservation).filter_by(user_id=user_id).delete()
        cursor.delete(user)
        cursor.commit()

    flash(f'Користувача видалено', 'success')
    return redirect(url_for('all_users'))



# Кошик
@app.route('/basket/update/<item_name>', methods=['POST'])
def update_basket(item_name):
    if request.form.get("csrf_token") != session["csrf_token"]:
        return "Запит заблоковано!", 403

    if not current_user.is_authenticated:
        flash("Для оформлення замовлення необхідно бути зареєстрованим")

    basket = session.get('basket', {})

    if item_name not in basket:
        flash("Товар не знайдено у кошику", "danger")
        return redirect(url_for('create_order'))

    qty = int(basket[item_name])
    action = request.form.get('action')

    if action == "plus":
        if qty < 10:
            basket[item_name] = qty + 1
        else:
            flash("Максимальна кількість - 10", "warning")

    elif action == "minus":
        if qty > 1:
            basket[item_name] = qty - 1
        else:
            flash("Мінімальна кількість - 1", "warning")

    elif action == "delete":
        basket.pop(item_name)

    session['basket'] = basket
    return redirect(url_for('create_order'))


@app.route('/basket/clear', methods=['POST'])
def clear_basket():
    if request.form.get("csrf_token") != session['csrf_token']:
        return "Запит заблоковано!", 403

    session.pop('basket', None)
    flash("Кошик очищено")

    return redirect(url_for('create_order'))



# Скидання пароля
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()

        with Session() as cursor:
            user = cursor.query(Users).filter_by(email=email).first()

        if user:
            # Генеруємо токен з поточним часом
            token = SERIALIZER.dumps(email, salt='password-reset')
            # URL для скидання пароля
            reset_url = url_for('reset_password', token=token, _external=True)
            email_reset_password(email, reset_url)

        flash('Якщо цей email зареєстровано - лист надіслано.', 'success')
        return redirect(url_for('forgot_password'))

    return render_template('forgot_password.html', csrf_token=session.get('csrf_token', ''))

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    # Перевіряємо токен
    try:
        email = SERIALIZER.loads(token, salt='password-reset', max_age=1800)  # 30 хв
    except Exception:
        flash('Посилання недійсне або застаріло.', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        new_password = request.form.get('password', '')
        confirm      = request.form.get('confirm', '')

        if len(new_password) < 8:
            flash('Пароль має бути не менше 8 символів.', 'danger')
            return redirect(request.url)

        if new_password != confirm:
            flash('Паролі не збігаються.', 'danger')
            return redirect(request.url)

        with Session() as cursor:
            user = cursor.query(Users).filter_by(email=email).first()
            if user:
                user.set_password(new_password)
                cursor.commit()
                flash('Пароль успішно змінено!', 'success')
                return redirect(url_for('login'))

    return render_template('reset_password.html',
                           token=token,
                           csrf_token=session.get('csrf_token', ''))



# Прив'язка телеграм
def generate_code():
    # Генерація випадкового коду
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

@app.route('/profile/telegram_link', methods=['POST'])
@login_required
def telegram_link():
    if request.form.get("csrf_token") != session["csrf_token"]:
        return "Запит заблоковано!", 403

    with Session() as cursor:
        # Видалити старий код якщо є
        old = cursor.query(TelegramCode).filter_by(user_id=current_user.id).first()
        if old:
            cursor.delete(old)
            cursor.flush()

        code = generate_code()
        cursor.add(TelegramCode(user_id=current_user.id, code=code))
        cursor.commit()

    session['telegram_code'] = code
    return redirect(url_for('profile'))

@app.route('/profile/telegram_unlink', methods=['POST'])
@login_required
def telegram_unlink():
    if request.form.get("csrf_token") != session["csrf_token"]:
        return "Запит заблоковано!", 403

    with Session() as cursor:
        user = cursor.query(Users).filter_by(id=current_user.id).first()
        user.telegram_chat_id = None
        cursor.commit()

    session.pop('telegram_code', None)
    flash("Telegram відв'язано.", 'success')
    return redirect(url_for('profile'))




if __name__ == '__main__':
    app.run(debug=True)