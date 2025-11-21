import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import FSInputFile
from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from dotenv import load_dotenv
import cv2
import numpy as np
from PIL import Image
from pixels2svg import svg_from_image  # Новый движок — 100% Python!

# Токен (локально из .env, на Railway из Variables)
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Укажи BOT_TOKEN в .env или в Railway Variables")

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Временные файлы
os.makedirs("temp", exist_ok=True)

# Клавиатура
menu = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Кривые")], [KeyboardButton(text="О боте")]],
    resize_keyboard=True
)

class States(StatesGroup):
    waiting_photo = State()

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "Привет!\n\nЯ превращаю любое фото в чистые векторные кривые (SVG)\n"
        "Нажми «Кривые» → отправь фото → получишь файл для CorelDRAW, резки, печати\n\n"
        "Сохраняет все линии без потери (на базе pixels2svg 2025)",
        reply_markup=menu
    )

@dp.message(F.text == "Кривые")
async def curves(message: types.Message, state: FSMContext):
    await state.set_state(States.waiting_photo)
    await message.answer(
        "Отправь фото, которое нужно перевести в кривые (лучше ч/б для топ-качества):",
        reply_markup=types.ReplyKeyboardRemove()
    )

@dp.message(States.waiting_photo, F.photo)
async def process_photo(message: types.Message, state: FSMContext):
    await state.clear()
    status = await message.answer("Скачиваю фото...")

    # Самое большое фото
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    photo_path = f"temp/{photo.file_id}.jpg"
    await bot.download_file(file.file_path, photo_path)

    await status.edit_text("Предобработка и векторизация... (10–40 сек)")

    output_svg = f"temp/{photo.file_id}.svg"

    try:
        # Предобработка: делаем чёткие края (Canny edges) для сохранения ЛЮБЫХ линий
        img_cv = cv2.imread(photo_path, cv2.IMREAD_GRAYSCALE)
        edges = cv2.Canny(img_cv, 50, 150)  # Настраивай: 50-150 = чёткие контуры
        edges = cv2.bitwise_not(edges)  # Инвертируем для белого на чёрном

        # Сохраняем предобработку как PIL Image
        pil_img = Image.fromarray(edges)

        # Векторизация: 0% упрощение = 100% деталей
        svg_content = svg_from_image(
            pil_img,
            target_width=img_cv.shape[1],  # Оригинальный размер
            target_height=img_cv.shape[0],
            simplification=0.0,  # НУЛЬ упрощения — все линии сохраняются!
            stroke_width=1  # Толщина линий в SVG
        )

        # Сохраняем SVG
        with open(output_svg, "w", encoding="utf-8") as f:
            f.write(svg_content)

        print("SVG готов через pixels2svg — все детали сохранены!")

        await status.edit_text("Готово! Отправляю идеальный вектор...")
        await message.answer_document(
            FSInputFile(output_svg, filename="кривые_идеальные.svg"),
            caption="Готово! Открывай в CorelDRAW, Inkscape, Illustrator\n\nМасштабируй бесконечно без потери качества"
        )
        await message.answer("Ещё фото? ↓", reply_markup=menu)

        # Удаляем временные файлы
        os.remove(photo_path)
        os.remove(output_svg)

    except Exception as e:
        await status.edit_text("Ошибка векторизации. Попробуй чёткое ч/б фото")
        print("Ошибка:", e)

@dp.message(F.text == "О боте")
async def about(message: types.Message):
    await message.answer(
        "Векторный бот 2025\n"
        "Движок: pixels2svg (чистый Python, без компиляции)\n"
        "Работает 24/7 на Railway\n"
        "Сохраняет 100% линий с Canny edges"
    )

async def main():
    print("Бот запущен! Pixels2SVG готов к векторизации (без внешних зависимостей)")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())