import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from bot.handlers.common import router as common_router
from bot.handlers.user import router as user_router
from bot.handlers.admin import router as admin_router
from dotenv import load_dotenv
import os


load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')


bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher(storage=MemoryStorage())

# Підключаємо роутери
dp.include_router(admin_router)
dp.include_router(common_router)
dp.include_router(user_router)

async def main():
    print("☢ Бот запущено...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())