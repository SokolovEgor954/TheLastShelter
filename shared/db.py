from sqlalchemy import create_engine, String, ForeignKey
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.sql.sqltypes import Boolean, DateTime
from sqlalchemy.testing.schema import mapped_column
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
from flask_login import UserMixin
import bcrypt
from datetime import datetime
from dotenv import load_dotenv
import os


load_dotenv()
PGUSER     = os.getenv('PGUSER')
PGPASSWORD = os.getenv('PGPASSWORD')

engine = create_engine(f"postgresql+psycopg2://{PGUSER}:{PGPASSWORD}@localhost:5432/online_restaurant", echo=True)
Session = sessionmaker(bind=engine)

class Base(DeclarativeBase):
    pass

class Users(Base, UserMixin):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    nickname: Mapped[str] = mapped_column(String(100), unique=True)
    password: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(50), unique=True)

    reservation = relationship("Reservation", foreign_keys="Reservation.user_id", back_populates="user")
    orders = relationship("Orders", foreign_keys="Orders.user_id", back_populates="user")
    telegram_chat_id: Mapped[int] = mapped_column(nullable=True)

    def set_password(self, password: str):
        self.password = bcrypt.hashpw(password.encode("utf8"), bcrypt.gensalt()).decode('utf8')

    def check_password(self, password: str) -> bool:
        return bcrypt.checkpw(password.encode("utf8"), self.password.encode("utf8"))

class Menu(Base):
    __tablename__ = "menu"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    weight: Mapped[int] = mapped_column(String)
    ingredients: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String)
    price: Mapped[int] = mapped_column(String)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    file_name: Mapped[str] = mapped_column(String)

    reviews = relationship("Reviews", back_populates="menu")

class Table(Base):
    __tablename__ = "tables"
    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[int] = mapped_column()          # номер столика
    type_table: Mapped[str] = mapped_column(String(10))
    label: Mapped[str] = mapped_column(String(50)) # "Біля вікна", "VIP", "Центр" тощо
    x: Mapped[int] = mapped_column()               # позиція X
    y: Mapped[int] = mapped_column()               # позиція Y

    reservations = relationship("Reservation", back_populates="table")


class Reservation(Base):
    __tablename__ = "reservation"
    id: Mapped[int] = mapped_column(primary_key=True)
    time_start: Mapped[datetime] = mapped_column(DateTime)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    table_id: Mapped[int] = mapped_column(ForeignKey("tables.id"))

    user = relationship("Users", back_populates="reservation")
    table = relationship("Table", back_populates="reservations")

class Orders(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_list: Mapped[str] = mapped_column(JSONB)
    order_time: Mapped[datetime] = mapped_column(DateTime)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20), default='new')

    user = relationship("Users", back_populates="orders")

class Reviews(Base):
    __tablename__ = "reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    menu_id: Mapped[int] = mapped_column(ForeignKey("menu.id"))
    rating: Mapped[int] = mapped_column()
    comment: Mapped[str] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("Users", foreign_keys=[user_id])
    menu = relationship("Menu", back_populates="reviews")

class TelegramCode(Base):
    __tablename__ = "telegram_codes"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    code: Mapped[str] = mapped_column(String(8), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("Users", foreign_keys=[user_id])

if __name__ == "__main__":
    Base.metadata.create_all(engine)