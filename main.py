import datetime

from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from MoodRecord import MoodRecord
from sqlite_db import db_start, insert_record, get_records, user_exists, delete_profile, create_profile, \
    get_week_records, get_profile, edit_profile

from config import TG_TOKEN


class ClientStatesGroup(StatesGroup):
    name = State()
    start_time = State()
    end_time = State()
    num_messages = State()

    deleting_profile = State()
    checking_mood = State()
    getting_description = State()

record = {}
new_profile = {}
commands = [
    ('start', 'Start the bot'),
    ('profile', 'See profile details'),
    ('del_profile', 'Delete your profile'),
    ('edit_profile', 'Edit your profile'),
    ('cancel', 'Cancel current operation'),
    ('help', 'Get help'),
]

bot = Bot(TG_TOKEN)
dp = Dispatcher(bot=bot, storage=MemoryStorage())

ikb = InlineKeyboardMarkup(row_width=2, one_time_keyboard=True)
ikb.add(InlineKeyboardButton('1', callback_data='1'), InlineKeyboardButton('2', callback_data='2'),
        InlineKeyboardButton('3', callback_data='3'), InlineKeyboardButton('4', callback_data='4'),
        InlineKeyboardButton('5', callback_data='5'))

del_ikb = InlineKeyboardMarkup(row_width=2, one_time_keyboard=True)
del_ikb.add(InlineKeyboardButton('No', callback_data='no'), InlineKeyboardButton('Yes', callback_data='yes'))

scheduler = AsyncIOScheduler()

user_id = None
chat_id = None


async def on_startup(_):
    print('Up and Running...')
    await db_start()


def check_time_format(time_str):
    try:
        hour, minute = time_str.split(':')
        hour_int, minute_int = map(int, time_str.split(':'))
        if (0 <= hour_int <= 23 and 0 <= minute_int <= 59) and len(minute) == 2:
            return True
        else:
            return False
    except ValueError:
        return False


@dp.message_handler(commands=['cancel'], state="*")
async def cancel_command(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is not None:
        await state.finish()
        await message.answer("Operation canceled.")
    else:
        await message.answer("There is no active operation to cancel.")

async def get_mood_record():
    global chat_id
    await ClientStatesGroup.checking_mood.set()
    await bot.send_message(chat_id=chat_id, text='Rate your Mood', reply_markup=ikb)


@dp.message_handler(commands=['del_profile'])
async def delete_profile_command(message: types.Message):
    await ClientStatesGroup.deleting_profile.set()
    await message.answer("If you delete your profile, all data will be lost. Continue anyway?",
                         reply_markup=del_ikb)


@dp.message_handler(commands=['edit_profile'])
async def edit_profile_command(message: types.Message):
    global user_id
    user_id = message.from_user.id
    await ClientStatesGroup.name.set()
    await message.answer("Ok, give me your name")

@dp.message_handler(commands=['profile'])
async def info_profile_command(message: types.Message):
    profile = await get_profile(message.from_user.id)
    info = f"User ID: {profile[0]}\nUsername: {profile[2]}\nLast modified: {profile[1].split(' ')[0]}\nDay starts: {profile[4]}\nDay ends: {profile[5]}\nMessages per day: {profile[6]}"
    await message.answer(info)

@dp.message_handler(lambda message: message.text, state=ClientStatesGroup.name)
async def save_name(message: types.message, state: FSMContext):
    given_name = message.text
    new_profile['name'] = given_name

    await ClientStatesGroup.next()
    await message.answer(
        f"Nice to meet you, {given_name}! Now I need to know what time you usually wake up, so I can send you messages according to your schedule. Time format is HH:MM. So, when do you start your day?")


@dp.message_handler(lambda message: message.text, state=ClientStatesGroup.start_time)
async def save_start_time(message: types.message, state: FSMContext):
    start_time = message.text
    if check_time_format(start_time):
        new_profile['start_time'] = start_time
        await ClientStatesGroup.next()
        await message.answer("Noted. When do you go to bed?")
    else:
        await message.reply("Please, try again")


@dp.message_handler(lambda message: message.text, state=ClientStatesGroup.end_time)
async def save_end_time(message: types.message, state: FSMContext):
    end_time = message.text
    if check_time_format(end_time):
        new_profile['end_time'] = end_time
        await ClientStatesGroup.next()
        await message.answer(
            f"How many times during the day do you want me to ask about your mood? Give me a number between 3 and 15. I'd recommend 5 messages per day")
    else:
        await message.reply("Please, try again")


@dp.message_handler(lambda message: message.text, state=ClientStatesGroup.num_messages)
async def save_num_messages(message: types.message, state: FSMContext):
    global chat_id
    chat_id = message.chat.id
    num_messages = message.text
    print(num_messages)
    if num_messages.isnumeric():
        if 16 > int(num_messages) > 2:
            new_profile['num_messages'] = int(num_messages)


            await edit_profile(user_id, new_profile['name'], datetime.datetime.now(), new_profile['start_time'], new_profile['end_time'], new_profile['num_messages'])
            await set_up_scheduler(new_profile['start_time'], new_profile['end_time'], new_profile['num_messages'])
            await message.answer(f"Profile created. In case you ever want to edit it use the /edit_profile command. When I send you a message rate your mood and then give me some context. Anything you find relevant")
            await state.finish()
    else:
        await message.reply("Please, try again")


@dp.message_handler(commands=['help'])
async def help_command(message: types.message):
    help_text = ''
    for el in commands:
        help_text += f"/{el[0]} - {el[1]}\n"
    await message.answer(help_text)


@dp.callback_query_handler(state=ClientStatesGroup.checking_mood)
async def mood_callback(callback: types.CallbackQuery, state: FSMContext):
    mood_val = callback.data
    record['mood_val'] = mood_val
    await bot.edit_message_reply_markup(chat_id=callback.from_user.id, reply_markup=None,
                                        message_id=callback.message.message_id)
    await bot.edit_message_text(chat_id=callback.from_user.id, message_id=callback.message.message_id,
                                text=f'{callback.message.text} - noted: {str(datetime.datetime.now()).split(".")[0]} - {mood_val}')
    await callback.message.answer("OK, give me a description")
    await ClientStatesGroup.next()


@dp.message_handler(state=ClientStatesGroup.getting_description)
async def get_description(message: types.message, state: FSMContext):
    desc = message.text
    record['description'] = desc
    await insert_record(MoodRecord(message.from_user.id, str(datetime.datetime.now().replace(microsecond=0)), record['mood_val'], record['description']))
    await message.answer("Noted")
    await state.finish()

@dp.callback_query_handler(state=ClientStatesGroup.deleting_profile)
async def profile_delete_callback(callback: types.CallbackQuery, state: FSMContext):
    should_del = callback.data
    await bot.edit_message_reply_markup(chat_id=callback.from_user.id, reply_markup=None,
                                        message_id=callback.message.message_id)
    if should_del == "yes":
        await delete_profile(callback.from_user.id)
        await callback.message.answer("Your profile was deleted")
    else:
        await callback.message.answer("No deleting - got it")
    await state.finish()

@dp.message_handler(commands=["records"])
async def display_records(message: types.message):
    records = await get_records(message.from_user.id)
    report = ""
    for record in records:
        report += f"{record[2].split('.')[0]} - {record[3]} - {record[4]}\n"

    await message.answer(report)

async def display_records_week():
    global user_id
    global chat_id

    records = await get_week_records(user_id)
    report = ""
    prev_day = None
    for record in records:
        dt_format = datetime.datetime.strptime(record[2], "%Y-%m-%d %H:%M:%S.%f")
        day_name = dt_format.strftime('%A')
        if prev_day == None:
            report += f"{day_name}\n"
        else:
            if prev_day != day_name:
                report += f'\n{day_name}\n'

        report += f"{dt_format.strftime('%H:%M')} - {record[3]} - {record[4]}\n"
        prev_day = day_name

    await bot.send_message(chat_id=chat_id, text=report)

async def set_up_scheduler(start, end, msg_per_day):
    scheduler.remove_all_jobs()
    h_start, m_start = map(int, start.split(':'))
    h_end, m_end = map(int, end.split(':'))

    start_total = h_start * 60 + m_start
    end_total = h_end * 60 + m_end

    total_time = ((24 * 60 - start_total) + end_total) * (end_total < start_total) + (end_total >= start_total) * (end_total - start_total)

    delta_time = total_time // msg_per_day

    start_total += 30
    print(delta_time)
    for i in range(msg_per_day):
        h = (start_total // 60) % 24
        m = start_total % 60
        print(f"{i}) {h}:{m}")
        scheduler.add_job(func=get_mood_record, trigger="cron", hour=h, minute=m, args=[])
        start_total += delta_time

    scheduler.add_job(func=display_records_week, trigger='cron', day_of_week = 6, hour=23, minute=30, args=[])

    if not scheduler.running:
        scheduler.start()


@dp.message_handler(commands=['start'], state=None)
async def start_command(message: types.Message):
    global user_id, chat_id
    user_id = message.from_user.id
    chat_id = message.chat.id

    exists = await user_exists(message.from_user.id)
    if exists:
        await message.answer("Welcome back!")
    else:
        await ClientStatesGroup.name.set()
        await message.answer("Welcome to Moody bot! I am here to help you track your mood throughout the week and send you reports. All I need from you is to answer my questions about your mood once in a while. You can use the /help command to read about all my commands. So, what's your name?")


if __name__ == '__main__':
    executor.start_polling(dispatcher=dp, skip_updates=True, on_startup=on_startup)
