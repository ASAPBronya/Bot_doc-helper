import sqlite3
from datetime import datetime, timedelta
from telebot import TeleBot, types
import re


TOKEN = '7288422892:AAG9OHjzN43ql8zFDdtwmE15d3H3xNUKdIc'
bot = TeleBot(TOKEN)

#SQLite
conn = sqlite3.connect('patients.db', check_same_thread=False)
cursor = conn.cursor()

# Таблица с пациентами
cursor.execute('''
CREATE TABLE IF NOT EXISTS patients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    dob DATE NOT NULL,
    date_added DATE NOT NULL
)
''')
conn.commit()

#Ввод от пользователя
state = {}
new_patient = {}


def reset_state(chat_id):
    if chat_id in state:
        del state[chat_id]
    if chat_id in new_patient:
        del new_patient[chat_id]


@bot.message_handler(commands=['start'])
def send_welcome(message):
    reset_state(message.chat.id)
    markup = types.InlineKeyboardMarkup()
    button1 = types.InlineKeyboardButton(text="1. Регистрировать нового пациента", callback_data="register")
    button2 = types.InlineKeyboardButton(text="2. Получить список пациентов на сегодня", callback_data="today")
    button3 = types.InlineKeyboardButton(text="3. Получить количество пациентов за каждый день недели",
                                         callback_data="report")
    markup.add(button1).add(button2).add(button3)  # Adding buttons in a column
    bot.send_message(message.chat.id, "Добро пожаловать! Пожалуйста, выберите действие:", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    if call.data == "register":
        bot.send_message(call.message.chat.id, "Пожалуйста, введите полное имя пациента:")
        state[call.message.chat.id] = 'awaiting_full_name'
    elif call.data == "today":
        list_today_patients(call.message)
    elif call.data == "report":
        week_report(call.message)
    elif state.get(call.message.chat.id) == 'confirm_full_name':
        if call.data == 'confirm_full_name_yes':
            bot.send_message(call.message.chat.id, "Пожалуйста, введите дату рождения (ГГГГ-ММ-ДД):")
            state[call.message.chat.id] = 'awaiting_dob'
        else:
            bot.send_message(call.message.chat.id, "Пожалуйста, введите полное имя пациента заново:")
            state[call.message.chat.id] = 'awaiting_full_name'
    elif state.get(call.message.chat.id) == 'confirm_dob':
        if call.data == 'confirm_dob_yes':
            full_name = new_patient[call.message.chat.id]['full_name']
            dob = new_patient[call.message.chat.id]['dob']
            date_added = datetime.now().date()
            cursor.execute("INSERT INTO patients (full_name, dob, date_added) VALUES (?, ?, ?)",
                           (full_name, dob, date_added))
            conn.commit()
            markup = types.InlineKeyboardMarkup()
            button_start = types.InlineKeyboardButton(text="Начать запись следующего пациента",
                                                      callback_data="register")
            button_today = types.InlineKeyboardButton(text="Получить список пациентов на сегодня",
                                                      callback_data="today")
            button_report = types.InlineKeyboardButton(text="Получить количество пациентов за неделю",
                                                       callback_data="report")
            markup.add(button_start).add(button_today).add(button_report)
            bot.send_message(call.message.chat.id, "Пациент успешно зарегистрирован!", reply_markup=markup)
            reset_state(call.message.chat.id)
        else:
            bot.send_message(call.message.chat.id, "Пожалуйста, введите дату рождения заново (ГГГГ-ММ-ДД):")
            state[call.message.chat.id] = 'awaiting_dob'


@bot.message_handler(func=lambda message: state.get(message.chat.id) == 'awaiting_full_name')
def get_full_name(message):
    full_name = message.text.strip()
    if re.match("^[А-ЯЁа-яёA-Za-z ]+$", full_name):
        new_patient[message.chat.id] = {'full_name': full_name}
        markup = types.InlineKeyboardMarkup()
        button_yes = types.InlineKeyboardButton(text="Да", callback_data="confirm_full_name_yes")
        button_no = types.InlineKeyboardButton(text="Нет", callback_data="confirm_full_name_no")
        markup.add(button_yes, button_no)
        bot.send_message(message.chat.id, f"Введено полное имя: {full_name}\nВерно?", reply_markup=markup)
        state[message.chat.id] = 'confirm_full_name'
    else:
        bot.send_message(message.chat.id,
                         "Неправильное полное имя. Пожалуйста, введите заново (только буквы и пробелы):")


@bot.message_handler(func=lambda message: state.get(message.chat.id) == 'awaiting_dob')
def get_dob(message):
    try:
        dob = datetime.strptime(message.text.strip(), '%Y-%m-%d').date()
        age = datetime.now().year - dob.year
        if age <= 100:
            new_patient[message.chat.id]['dob'] = str(dob)
            markup = types.InlineKeyboardMarkup()
            button_yes = types.InlineKeyboardButton(text="Да", callback_data="confirm_dob_yes")
            button_no = types.InlineKeyboardButton(text="Нет", callback_data="confirm_dob_no")
            markup.add(button_yes, button_no)
            bot.send_message(message.chat.id, f"Введена дата рождения: {dob}\nВерно?", reply_markup=markup)
            state[message.chat.id] = 'confirm_dob'
        else:
            bot.send_message(message.chat.id,
                             "Недопустимый возраст (должно быть не более 100 лет). Пожалуйста, введите заново (ГГГ-ММ-ДД):")
    except ValueError:
        bot.send_message(message.chat.id, "Неправильный формат даты. Пожалуйста, введите заново (ГГГГ-ММ-ДД):")


@bot.message_handler(commands=['today'])
def list_today_patients(message):
    today = datetime.now().date()
    cursor.execute("SELECT full_name, dob FROM patients WHERE date_added = ?", (today,))
    patients = cursor.fetchall()
    if patients:
        response = "Пациенты на сегодня:\n"
        for patient in patients:
            response += f"{patient[0]}, Дата рождения: {patient[1]}\n"
        bot.send_message(message.chat.id, response)
    else:
        bot.send_message(message.chat.id, "Сегодня пациентов не было.")

    # кнопки после отправки списка пациентов
    markup = types.InlineKeyboardMarkup()
    button_register = types.InlineKeyboardButton(text="Записать нового пациента", callback_data="register")
    button_report = types.InlineKeyboardButton(text="Получить количество пациентов за неделю", callback_data="report")
    markup.add(button_register).add(button_report)
    bot.send_message(message.chat.id, "Выберите следующее действие:", reply_markup=markup)


@bot.message_handler(commands=['report'])
def week_report(message):
    today = datetime.now().date()
    response = "Количество пациентов за последнюю неделю:\n"
    for i in range(7):
        date = today - timedelta(days=i)
        cursor.execute("SELECT COUNT(*) FROM patients WHERE date_added = ?", (date,))
        count = cursor.fetchone()[0]
        response += f"{date}: {count} пациентов\n"
    bot.send_message(message.chat.id, response)

    #кнопки после списка за неделю
    markup = types.InlineKeyboardMarkup()
    button_register = types.InlineKeyboardButton(text="Записать нового пациента", callback_data="register")
    button_today = types.InlineKeyboardButton(text="Получить список пациентов на сегодня", callback_data="today")
    markup.add(button_register).add(button_today)
    bot.send_message(message.chat.id, "Выберите следующее действие:", reply_markup=markup)


@bot.message_handler(func=lambda message: True)
def handle_message(message):
    text = message.text.strip()
    if text == '1':
        bot.send_message(message.chat.id, "Пожалуйста, введите полное имя пациента:")
        state[message.chat.id] = 'awaiting_full_name'
    elif text == '2':
        list_today_patients(message)
    elif text == '3':
        week_report(message)
    else:
        markup = types.InlineKeyboardMarkup()
        button1 = types.InlineKeyboardButton(text="1. Регистрировать нового пациента", callback_data="register")
        button2 = types.InlineKeyboardButton(text="2. Получить список пациентов на сегодня", callback_data="today")
        button3 = types.InlineKeyboardButton(text="3. Получить количество пациентов за каждый день недели",
                                             callback_data="report")
        markup.add(button1).add(button2).add(button3)
        bot.send_message(message.chat.id, "Недопустимый вариант. Пожалуйста, выберите действие:", reply_markup=markup)


if __name__ == '__main__':
    bot.polling(none_stop=True)