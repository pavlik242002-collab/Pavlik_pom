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
        "Нажми «Кривые» → отправь фото → получишь файл для CorelDRAW, резки, печати",
        reply_markup=menu
    )

@dp.message(F.text == "Кривые")
async def curves(message: types.Message, state: FSMContext):
    await state.set_state(States.waiting_photo)
    await message.answer(
        "Отправь фото, которое нужно перевести в кривые:",
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

    await status.edit_text("Векторизация... (15–50 сек)")

    output_svg = f"temp/{photo.file_id}.svg"

    try:
        from PIL import Image
        import numpy as np
        import pypotrace

        # Открываем и делаем чёткое ч/б (это ключ к отличному результату)
        img = Image.open(photo_path).convert("L")
        img = img.point(lambda x: 0 if x < 128 else 255, "1")  # жёсткий порог

        # pypotrace
        bmp = pypotrace.Bitmap(np.array(img))
        path = bmp.trace(
            turdsize=1,
            turnpolicy=pypotrace.TURNPOLICY_MINORITY,
            alphamax=1.0,
            opticurve=True,
            opttolerance=0.2
        )

        # Записываем SVG
        with open(output_svg, "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write('<svg xmlns="http://www.w3.org/2000/svg" version="1.1" ')
            f.write(f'width="{img.width}px" height="{img.height}px" viewBox="0 0 {img.width} {img.height}">\n')
            f.write('<g transform="scale(1,-1) translate(0,-{img.height})">\n')

            for curve in path:
                d = f"M{curve.start_point.x},{curve.start_point.y}"
                for segment in curve:
                    if segment.is_corner:
                        d += f" L{segment.c.x},{segment.c.y} L{segment.end_point.x},{segment.end_point.y}"
                    else:
                        d += f" C{segment.c1.x},{segment.c1.y} {segment.c2.x},{segment.c2.y} {segment.end_point.x},{segment.end_point.y}"
                d += " Z"
                f.write(f'<path d="{d}" fill="black"/>\n')
            f.write('</g></svg>\n')

        await status.edit_text("Готово! Отправляю вектор...")
        await message.answer_document(
            FSInputFile(output_svg, filename="кривые_идеальные.svg"),
            caption="Готово! Открывай в CorelDRAW, Inkscape, Illustrator"
        )
        await message.answer("Ещё фото? ↓", reply_markup=menu)

        # Удаляем временные файлы
        os.remove(photo_path)
        os.remove(output_svg)

    except Exception as e:
        await status.edit_text("Ошибка векторизации. Попробуй другое фото")
        print("Ошибка:", e)

@dp.message(F.text == "О боте")
async def about(message: types.Message):
    await message.answer("Векторный бот 2025\nРаботает 24/7 на Railway\nДвижок: pypotrace (чистый Python)")

async def main():
    print("Бот запущен и работает 24/7 на Railway!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())