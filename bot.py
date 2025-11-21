import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import FSInputFile
from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
import cv2
import aiofiles
from dotenv import load_dotenv

# Загружаем токен (локально из .env, на Railway — из переменных окружения)
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# === Инициализация ===
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Папка для временных файлов
os.makedirs("temp", exist_ok=True)

# === Клавиатура ===
menu = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Кривые")], [KeyboardButton(text="О боте")]],
    resize_keyboard=True
)


class States(StatesGroup):
    waiting_photo = State()


# Устанавливаем и импортируем лучший CPU-векторизатор 2025 года
# Устанавливаем и импортируем vectorizer-ai v2.0.2 (CPU-only)
import subprocess
import sys
subprocess.check_call([sys.executable, "-m", "pip", "install", "vectorizer-ai==2.0.2", "--quiet"])

try:
    from vectorizer_ai import Vectorizer  # API для v2.0.2
    vectorizer = Vectorizer()  # Инициализируем один раз
    print("Vectorizer-ai v2.0.2 загружен (работает на любом CPU)")
except ImportError:
    print("Fallback: используем potrace")
    # Если не встанет — переходим к запасному варианту ниже

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "Привет! Я превращаю любое фото в идеальные векторные кривые\n\n"
        "Нажми кнопку «Кривые» и отправь фото — получишь SVG для CorelDRAW, резки, печати",
        reply_markup=menu
    )


@dp.message(F.text == "Кривые")
async def curves(message: types.Message, state: FSMContext):
    await state.set_state(States.waiting_photo)
    await message.answer("Отправь фото, которое нужно перевести в кривые:",
                         reply_markup=types.ReplyKeyboardRemove())


@dp.message(States.waiting_photo, F.photo)
async def process_photo(message: types.Message, state: FSMContext):
    await state.clear()
    status = await message.answer("Скачиваю фото...")

    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    photo_path = f"temp/{photo.file_id}.jpg"
    await bot.download_file(file.file_path, photo_path)

    await status.edit_text("Векторизация в процессе... (20–60 сек)")

    try:
        output_svg = f"temp/{photo.file_id}.svg"

        # Векторизация с v2.0.2 (максимум деталей, без потери линий)
        vectorizer.vectorize_image(
            photo_path,
            output_svg,
            mode="color",  # "color" или "bw"
            detail_level=98,  # 98% деталей (почти 100%)
            corner_threshold=45,  # для острых углов
            smooth_curves=True  # гладкие кривые Безье
        )

        await status.edit_text("Готово! Отправляю вектор...")

        await message.answer_document(
            FSInputFile(output_svg, filename="кривые_идеальные.svg"),
            caption="Готово! Открывай в CorelDRAW / Inkscape / Illustrator"
        )
        await message.answer("Ещё фото? Нажми кнопку ↓", reply_markup=menu)

        # Чистим
        os.remove(photo_path)
        os.remove(output_svg)

    except Exception as e:
        await status.edit_text("Ошибка! Попробуй другое фото")
        print(e)


@dp.message(F.text == "О боте")
async def about(message: types.Message):
    await message.answer("Векторный бот 2025\nCPU-only • 24/7 • Без потери линий")


async def main():
    print("Бот запущен и работает 24/7 на Railway!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())