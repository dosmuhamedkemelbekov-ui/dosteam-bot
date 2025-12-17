# ... (все импорты и конфигурация до инициализации бота остаются без изменений)
import asyncio
import logging
import gspread
from oauth2client.service_account import ServiceAccountCredentials

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardButton, 
    ReplyKeyboardRemove, BotCommand, BotCommandScopeChat
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

# НОВЫЙ ИМПОРТ для прокси
from aiogram.client.session.aiohttp import AiohttpSession

# --- КОНФИГУРАЦИЯ ---
BOT_TOKEN = "8402030731:AAEEx7dVLHZCjgRelF0CLDtz4AB2DxunFCQ"
ADMIN_IDS = [877202193]
SHEET_NAME = "DOSTEAM Bot Database" 

logging.basicConfig(level=logging.INFO)
storage = MemoryStorage()

# --- GOOGLE SHEETS ИНТЕГРАЦИЯ (без изменений) ---
try:
    scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open(SHEET_NAME)
    users_ws = sheet.worksheet("Лист1")
    events_ws = sheet.worksheet("Events")
    shop_ws = sheet.worksheet("Shop")
    logging.info("Успешное подключение к Google Sheets.")
except Exception as e:
    logging.error(f"Ошибка подключения к Google Sheets: {e}")
    users_ws = events_ws = shop_ws = None

# ... (все функции для работы с Google Sheets gs_... остаются без изменений)
def gs_add_user(user_id: int, username: str, name: str, faculty_course: str):
    if not users_ws: return
    row = [user_id, username, name, faculty_course, 0]
    users_ws.append_row(row)

def gs_get_user(user_id: int):
    if not users_ws: return None
    all_users = users_ws.get_all_records()
    for user in all_users:
        if user['user_id'] == user_id:
            return user
    return None

def gs_get_user_by_username(username: str):
    if not users_ws: return None
    clean_username = username.lstrip('@')
    all_users = users_ws.get_all_records()
    for user in all_users:
        if user['username'] == clean_username:
            return user
    return None

def gs_update_balance(user_id: int, amount: int):
    if not users_ws: return
    try:
        cell = users_ws.find(str(user_id))
        current_balance = int(users_ws.cell(cell.row, 5).value)
        new_balance = current_balance + amount
        users_ws.update_cell(cell.row, 5, new_balance)
    except (gspread.exceptions.CellNotFound, AttributeError):
        logging.error(f"Не удалось обновить баланс: пользователь {user_id} не найден в таблице.")

def gs_add_event(name: str, event_date: str):
    if not events_ws: return
    events_ws.append_row([name, event_date])

def gs_get_events():
    if not events_ws: return []
    return events_ws.get_all_records()

def gs_get_shop_items():
    if not shop_ws: return []
    return shop_ws.get_all_records()

def gs_get_shop_item(item_id: int):
    if not shop_ws: return None
    all_items = shop_ws.get_all_records()
    for item in all_items:
        if item['id'] == item_id:
            return item
    return None

# --- FSM (без изменений) ---
class Registration(StatesGroup):
    waiting_for_name = State()
    waiting_for_faculty_course = State()

# --- ИНИЦИАЛИЗАЦИЯ БОТА (БЕЗ ПРОКСИ, ДЛЯ ЛОКАЛЬНОГО ЗАПУСКА) ---
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)

# --- (Весь остальной код обработчиков команд остается БЕЗ ИЗМЕНЕНИЙ) ---
async def set_bot_commands(bot: Bot):
    # ... (код без изменений)
    user_commands = [
        BotCommand(command="command1", description="▶️ Старт и регистрация"),
        BotCommand(command="command2", description="💰 Мой баланс"),
        BotCommand(command="command3", description="📅 Мероприятия"),
        BotCommand(command="command4", description="🛒 Магазин")
    ]
    admin_commands = user_commands + [
        BotCommand(command="command5", description="👑 Начислить коины"),
        BotCommand(command="command6", description="👑 Снять коины"),
        BotCommand(command="command7", description="👑 Добавить мероприятие")
    ]
    await bot.set_my_commands(user_commands)
    for admin_id in ADMIN_IDS:
        await bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=admin_id))

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

@dp.message(Command("command1"))
async def cmd_start(message: Message, state: FSMContext):
    user = gs_get_user(message.from_user.id)
    if user:
        await message.answer(f"👋 С возвращением, {user['name']}!\nЯ бот DOS Team Community.")
    else:
        await message.answer("Добро пожаловать в DOS Team Community!\nДавайте зарегистрируемся. Пожалуйста, введите ваше имя и фамилию:")
        await state.set_state(Registration.waiting_for_name)
# ... (все остальные обработчики без изменений)
@dp.message(StateFilter(Registration.waiting_for_name))
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Отлично! Теперь введите ваш факультет и курс (например, ИСиТ-21):")
    await state.set_state(Registration.waiting_for_faculty_course)

@dp.message(StateFilter(Registration.waiting_for_faculty_course))
async def process_faculty_course(message: Message, state: FSMContext):
    user_data = await state.get_data()
    name = user_data['name']
    faculty_course = message.text
    user_id = message.from_user.id
    username = message.from_user.username or ""
    gs_add_user(user_id, username, name, faculty_course)
    await message.answer(f"🎉 Регистрация успешно завершена!\nИмя: {name}\nФакультет/курс: {faculty_course}\n\nНачните с команды /command2.", reply_markup=ReplyKeyboardRemove())
    await state.clear()

@dp.message(Command("command2"))
async def cmd_balance(message: Message):
    user = gs_get_user(message.from_user.id)
    if user:
        await message.answer(f"💰 Ваш текущий баланс: {user['balance']} DC Coins.")
    else:
        await message.answer("Вы еще не зарегистрированы. Пожалуйста, используйте команду /command1.")

@dp.message(Command("command3"))
async def cmd_events(message: Message):
    events = gs_get_events()
    if events:
        response = "📅 Предстоящие мероприятия:\n\n"
        for event in events:
            response += f"🔹 **{event['name']}** - {event['event_date']}\n"
        await message.answer(response, parse_mode="Markdown")
    else:
        await message.answer("Пока нет запланированных мероприятий.")

@dp.message(Command("command4"))
async def cmd_shop(message: Message):
    items = gs_get_shop_items()
    if not items:
        await message.answer("😔 В магазине пока пусто.")
        return
    builder = InlineKeyboardBuilder()
    for item in items:
        builder.add(InlineKeyboardButton(text=f"{item['name']} - {item['price']} DC", callback_data=f"buy_{item['id']}"))
    builder.adjust(1)
    await message.answer("🛒 Добро пожаловать в магазин! Выберите товар для покупки:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("buy_"))
async def process_buy_callback(callback: CallbackQuery):
    item_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    user = gs_get_user(user_id)
    item = gs_get_shop_item(item_id)
    if not user or not item:
        await callback.answer("Ошибка: пользователь или товар не найден.", show_alert=True)
        return
    user_balance = int(user['balance'])
    item_price = int(item['price'])
    if user_balance >= item_price:
        gs_update_balance(user_id, -item_price)
        await callback.message.edit_text(f"✅ Вы успешно приобрели '{item['name']}'! Ваш баланс обновлен.")
        await callback.answer("Покупка совершена!")
    else:
        await callback.answer(f"Недостаточно средств! Вам не хватает {item_price - user_balance} DC.", show_alert=True)

@dp.message(Command("command5"))
async def cmd_addcoins(message: Message, command: CommandObject):
    if not is_admin(message.from_user.id): return
    if not command.args:
        await message.answer("⚠️ Пример:\n/command5 @ник 100")
        return
    try:
        args = command.args.split()
        username = args[0]
        amount = int(args[1])
        user = gs_get_user_by_username(username)
        if user:
            user_id = user['user_id']
            gs_update_balance(user_id, amount)
            await message.answer(f"✅ Пользователю {username} успешно начислено {amount} DC Coins.")
            try:
                await bot.send_message(user_id, f"🎉 Вам было начислено {amount} DC Coins!")
            except Exception as e:
                logging.error(f"Не удалось отправить уведомление: {e}")
        else:
            await message.answer(f"❌ Пользователь {username} не найден. Он должен сначала запустить бота.")
    except (IndexError, ValueError):
        await message.answer("⚠️ Неверный формат: /command5 @username <количество>")

@dp.message(Command("command6"))
async def cmd_removecoins(message: Message, command: CommandObject):
    if not is_admin(message.from_user.id): return
    if not command.args:
        await message.answer("⚠️ Пример:\n/command6 @ник 50")
        return
    try:
        args = command.args.split()
        username = args[0]
        amount = -int(args[1])
        user = gs_get_user_by_username(username)
        if user:
            user_id = user['user_id']
            gs_update_balance(user_id, amount)
            await message.answer(f"✅ У пользователя {username} успешно снято {-amount} DC Coins.")
        else:
            await message.answer(f"❌ Пользователь {username} не найден.")
    except (IndexError, ValueError):
        await message.answer("⚠️ Неверный формат: /command6 @username <количество>")

@dp.message(Command("command7"))
async def cmd_addevent(message: Message, command: CommandObject):
    if not is_admin(message.from_user.id): return
    if not command.args:
        await message.answer("⚠️ Пример:\n/command7 Название; Дата")
        return
    try:
        args = command.args.split(';')
        name = args[0].strip()
        event_date = args[1].strip()
        gs_add_event(name, event_date)
        await message.answer(f"✅ Мероприятие '{name}' успешно добавлено на дату {event_date}.")
    except IndexError:
        await message.answer("⚠️ Неверный формат: /command7 Название; ДД.ММ.ГГГГ")
        
async def main():
    if not users_ws:
        logging.critical("Не удалось подключиться к Google Sheets. Бот не может быть запущен.")
        return
    
    await set_bot_commands(bot)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())