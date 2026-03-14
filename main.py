import asyncio
import logging
import os
from aiohttp import web

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, BotCommand
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

from config import config
from database import Database
from admin import router as admin_router
from user_handlers import router as user_router
from utils import check_subscription, format_movie_info, send_movie_with_caption, validate_movie_code
from keyboards import get_main_menu_kb, get_movie_actions_kb

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

db = Database(config.DATABASE_URL)
bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()

# ---------------- WEB SERVER (Render uchun) ----------------

async def handle(request):
    return web.Response(text="Bot ishlayapti!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)

    port = int(os.environ.get("PORT", 10000))

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# ---------------- BOT HANDLERS ----------------

@dp.message(CommandStart())
async def cmd_start(message: Message, db: Database, state: FSMContext):

    await state.clear()

    await db.add_user(
        message.from_user.id,
        message.from_user.username or "",
        message.from_user.first_name or ""
    )

    is_subscribed, kb = await check_subscription(message.from_user.id, db, bot)

    if not is_subscribed:
        await message.answer(
            "Botdan foydalanish uchun kanallarga obuna bo'ling",
            reply_markup=kb
        )
        return

    await message.answer(
        "Kino kodini yuboring 🎬",
        reply_markup=get_main_menu_kb()
    )

@dp.message(F.text.isdigit())
async def handle_movie_code(message: Message, db: Database):

    movie_code = validate_movie_code(message.text)

    if not movie_code:
        await message.answer("Noto'g'ri kod")
        return

    movie = await db.get_movie_by_code(movie_code)

    if not movie:
        await message.answer("Bunday kino topilmadi")
        return

    rating = await db.get_movie_rating(movie.id)

    caption = format_movie_info(movie, rating)

    await send_movie_with_caption(
        bot,
        message.from_user.id,
        movie,
        caption,
        reply_markup=get_movie_actions_kb(movie_code, False)
    )

# ---------------- BOT COMMANDS ----------------

async def set_bot_commands():

    commands = [
        BotCommand(command="start", description="Botni ishga tushirish"),
        BotCommand(command="search", description="Kino qidirish"),
        BotCommand(command="top", description="Top kinolar"),
        BotCommand(command="new", description="Yangi kinolar"),
    ]

    await bot.set_my_commands(commands)

# ---------------- STARTUP ----------------

async def on_startup():

    logger.info("Bot ishga tushmoqda")

    await db.init_db()

    await set_bot_commands()

    try:
        await bot.send_message(config.ADMIN_ID, "Bot ishga tushdi")
    except:
        pass

# ---------------- MAIN ----------------

async def main():

    dp.include_router(admin_router)
    dp.include_router(user_router)

    dp["db"] = db
    dp["config"] = config

    dp.startup.register(on_startup)

    asyncio.create_task(start_web_server())

    await dp.start_polling(bot)

# ---------------- RUN ----------------

if __name__ == "__main__":

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot to'xtatildi")
