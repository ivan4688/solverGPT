# coding: utf-8
# !/usr/bin/env python3
import json
import logging
import threading
import time
from datetime import datetime
from typing import Optional, Set, Dict
import os
import sys
import io
from PIL import Image

import telebot
from telebot import types

from src.solver import build_model_prompt, query, query_inline, build_model_inline, prompt_web, query_web
import src.saver as st

BOT_USERNAME = "solve_ai_bot"
policy = """
Настоящее Пользовательское соглашение регулирует отношения между вами и  администрацией бота касательно использования вами Telegram-бота @solve_ai_bot

1. Общие положения

1.1. Начиная использовать Бота любым способом, вы подтверждаете, что полностью ознакомились и приняли условия настоящего Соглашения.

1.2. Администрация оставляет за собой право блокировать любого пользователя бота на их усмотрение. 

1.3. Разработчик вправе в одностороннем порядке изменять настоящее Соглашение.

2. Условия использования

2.1. Вы обязуетесь использовать Бота исключительно в законных целях и не нарушать права третьих лиц.

2.2. Вам запрещается:

    *   Использовать Бота для создания, распространения или продвижения контента, который является незаконным, вредоносным, угрожающим, клеветническим, оскорбительным, порнографическим, разжигающим ненависть или дискриминацию по расовому, этническому, половому или иному признаку.

    *   Запрашивать или генерировать контент, содержащий инструкции по совершению противозаконных действий, созданию оружия или вредоносного программного обеспечения.

    *   Выдавать себя за другое лицо или распространять персональные данные третьих лиц без их согласия.

    *   Использовать Бота для автоматизированного сбора данных (спама, парсинга) или для атак на другие системы.

    *   Попытаться обойти защиту или изменить исходный код Бота.

3. Интеллектуальная собственность

3.1. Все права на сам Бот, его дизайн, логотип и уникальный код принадлежат Разработчику.

3.2. Техология искусственного интеллекта, лежащая в основе Бота, предоставляется сторонним провайдером (например, OpenAI), и ее использование регулируется соответствующими лицензионными соглашениями.

3.3. Сгенерированный Ботом текст предоставляется вам на условиях лицензии. Вы становитесь правообладателем сгенерированного текста и можете использовать его в любых законных целях, включая коммерческие, за исключением случаев, прямо указанных в п. 3.4.

3.4. Вы не имеете права использовать сгенерированный контент для:

    *   Создания конкурирующего сервиса, основанного на том же ИИ.

    *   Обучения других моделей искусственного интеллекта без явного разрешения от Разработчика и провайдера ИИ.

    *   Распространения контента, который нарушает настоящее Соглашение.

4. Отказ от ответственности

4.1. Бот и все сгенерированные им материалы предоставляются по принципу «как есть» (AS IS). Разработчик не дает никаких явных или подразумеваемых гарантий относительно точности, полноты, надежности или пригодности контента для каких-либо конкретных целей.

4.2. Разработчик не несет ответственности за любые прямые или косвенные убытки, возникшие в результате использования или невозможности использования Бота, включая, но не ограничиваясь: упущенную выгоду, потерю данных или бизнеса, а также за действия, предпринятые вами на основе сгенерированного Ботом контента.

4.3. Пользователь несет полную ответственность за контент, который он создает с помощью Бота, и за последствия его использования.

5. Конфиденциальность

5.1. Для работы Бота мы можем собирать и обрабатывать данные, которые вы ему предоставляете, включая тексты ваших запросов. Эти данные используются исключительно для генерации ответа и улучшения работы сервиса.

5.2. Мы не передаем ваши персональные данные и текст запросов третьим лицам, за исключением случаев, предусмотренных законом, или для обеспечения работы технологий ИИ (например, передача запроса в API OpenAI).

6. Прекращение доступа

6.1. Разработчик вправе в одностороннем порядке, без объяснения причин и без предварительного уведомления, ограничить или полностью прекратить ваш доступ к Боту в случае нарушения вами условий настоящего Соглашения.

7. Контактная информация

По всем вопросам, связанным с использованием Бота и настоящим Соглашением, вы можете связаться с нами: @VanYyOp / @pydev_ai
"""

faq = """
Привет! Это FAQ по использованию бота. 

1. Пожалуйста ознакомьтесь с пользовательским соглашением бота

2. По всем вопросам обращайтесь к @pydev_ai

Итак:

Для начала работы с ботом нажмите /start после чего вы можете вводить ваши запросы. 

Запросы могут включать:

1. Текст 

2. Изображения (.png, .jpg, .jpeg, .ttf) 

3. Документы (.docx, .pdf) 

4. Скрипты (.py) 

5. Таблицы (любые excel) 

После запроса вы должны подождать и получите ответ нейросети на ваш запрос 

Используемые нейросети:

1. Deepseek V3 780b

2. Yandex Vision OCR 

3. GPT-oss 120b

Полезные команды:

1. /faq | /help - вызывает меню где вы еще раз можете прочитать этот текст

2. /support - связь с тех поддержкой бота

3. /policy - пользовательское соглашение. 
    """

# ----- Logging -----
logger = logging.getLogger("tg_bot")
logger.setLevel(logging.INFO)
fh = logging.FileHandler("bot.log", encoding="utf-8")
fh.setFormatter(logging.Formatter('%(asctime)s | %(levelname)s | %(message)s', "%Y-%m-%d %H:%M:%S"))
logger.addHandler(fh)
logger.addHandler(logging.StreamHandler())


# ----- Token loading -----
def load_token(path: str = "apis/tg_api.json") -> Optional[str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data.get("token") or data.get("TOKEN") or next(iter(data.values()), None)
            return str(data)
    except Exception:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            return None


TOKEN = load_token()
if not TOKEN:
    raise RuntimeError("Token not found in tg_api.json")

bot = telebot.TeleBot(TOKEN)

# ----- Persistent known users -----
KNOWN_FILE = "known_users.json"
_known_lock = threading.Lock()

# ----- Banned users -----
BANNED_FILE = "banned_users.json"
_banned_lock = threading.Lock()


def load_known_users() -> Set[int]:
    try:
        if os.path.exists(KNOWN_FILE):
            with open(KNOWN_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(int(x) for x in data)
    except Exception:
        logger.exception("load_known_users failed")
    return set()


def save_known_users(s: Set[int]):
    try:
        with open(KNOWN_FILE, "w", encoding="utf-8") as f:
            json.dump(list(s), f, ensure_ascii=False)
    except Exception:
        logger.exception("save_known_users failed")


def load_banned_users() -> Set[int]:
    try:
        if os.path.exists(BANNED_FILE):
            with open(BANNED_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(int(x) for x in data)
    except Exception:
        logger.exception("load_banned_users failed")
    return set()


def save_banned_users(s: Set[int]):
    try:
        with open(BANNED_FILE, "w", encoding="utf-8") as f:
            json.dump(list(s), f, ensure_ascii=False)
    except Exception:
        logger.exception("save_banned_users failed")


known_users: Set[int] = load_known_users()
banned_users: Set[int] = load_banned_users()

# ----- In-memory meta and stats -----
users_meta: Dict[int, str] = {}
request_stats: Dict[int, int] = {}
total_requests = 0

# ----- Admin list -----
ADMIN_USERNAMES = {"vanyyop", "pydev_ai"}


def is_admin(user) -> bool:
    if not user:
        return False
    un = getattr(user, "username", None)
    if not un:
        return False
    return un.lstrip("@").lower() in ADMIN_USERNAMES


def is_banned(user_id: int) -> bool:
    return user_id in banned_users


def keyboard_start() -> types.ReplyKeyboardMarkup:
    kb = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    kb.add(types.KeyboardButton("Tech support 🛡"), types.KeyboardButton("Info 📜"))
    kb.add(types.KeyboardButton("Channel 👀"))
    kb.add(types.KeyboardButton("Поиск в интернете 🌍"))  # кнопка web в стартовом меню
    return kb

def keyboard_web_mode() -> types.ReplyKeyboardMarkup:
    kb = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    kb.add(types.KeyboardButton("Меню ⏬"))
    return kb


def log_line(user, req: str, bot_answer: Optional[str]):
    uname = f"@{user.username}" if getattr(user, "username", None) else (user.first_name or str(user.id))
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    short_ans = bot_answer if bot_answer is None else (
            bot_answer[:800] + ("...[truncated]" if len(bot_answer) > 800 else ""))
    logger.info(f"{ts} | {uname} | {req} | {short_ans}")


def register_user(message):
    try:
        uid = message.from_user.id
        with _known_lock:
            if uid not in known_users:
                known_users.add(uid)
                save_known_users(known_users)
        users_meta[uid] = f"@{message.from_user.username}" if getattr(message.from_user, "username", None) else (
                message.from_user.first_name or str(uid))
    except Exception:
        logger.exception("register_user failed")


def normalize_image(image_path: str, max_size_mb: int = 1) -> str:
    max_size_bytes = max_size_mb * 1024 * 1024

    try:
        with Image.open(image_path) as img:
            # Конвертируем в RGB если нужно (для JPEG)
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')

            # Проверяем текущий размер
            current_size = os.path.getsize(image_path)

            if current_size <= max_size_bytes:
                return image_path  # Размер уже подходит

            # Параметры сжатия
            quality = 85
            original_format = img.format

            # Пробуем уменьшить качество
            while quality > 30 and current_size > max_size_bytes:
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG', quality=quality, optimize=True)
                current_size = buffer.getbuffer().nbytes
                quality -= 5

            # Если все еще большой размер, уменьшаем разрешение
            if current_size > max_size_bytes:
                width, height = img.size
                scale_factor = 0.8

                while current_size > max_size_bytes and scale_factor > 0.3:
                    new_width = int(width * scale_factor)
                    new_height = int(height * scale_factor)

                    if new_width < 100 or new_height < 100:
                        break

                    resized_img = img.resize((new_width, new_height), Image.LANCZOS)
                    buffer = io.BytesIO()
                    resized_img.save(buffer, format='JPEG', quality=70, optimize=True)
                    current_size = buffer.getbuffer().nbytes
                    scale_factor -= 0.1
                    img = resized_img

            # Сохраняем нормализованное изображение
            normalized_path = image_path.replace('.', '_normalized.')
            if 'normalized' not in normalized_path:
                normalized_path = image_path.rsplit('.', 1)[0] + '_normalized.jpg'

            if hasattr(img, 'format') and img.format == 'JPEG':
                img.save(normalized_path, 'JPEG', quality=max(quality, 50), optimize=True)
            else:
                img.save(normalized_path, 'JPEG', quality=70, optimize=True)

            final_size = os.path.getsize(normalized_path)
            logger.info(f"Image normalized: {current_size / 1024 / 1024:.2f}MB -> {final_size / 1024 / 1024:.2f}MB")

            return normalized_path

    except Exception as e:
        logger.error(f"Error normalizing image {image_path}: {e}")
        return image_path  # Возвращаем оригинал в случае ошибки


def find_user_id(username: str) -> Optional[int]:
    """Находит user_id по username"""
    username = username.lstrip('@').lower()
    for uid, meta in users_meta.items():
        if meta.lstrip('@').lower() == username:
            return uid
    return None


@bot.message_handler(commands=['start'])
def cmd_start(message):
    if is_banned(message.from_user.id):
        bot.send_message(message.chat.id, "❌ Вы заблокированы и не можете использовать бота.")
        return

    register_user(message)
    bot.send_message(message.chat.id, f"Привет, {message.from_user.first_name or 'юзер'}!\nЯ - твой ИИ ассистент, помогу тебе с любым вопросом\nТолько напиши...",
                     reply_markup=keyboard_start())
    log_line(message.from_user, "/start", "sent greeting")


@bot.message_handler(commands=['support'])
def cmd_support(message):
    if is_banned(message.from_user.id):
        return

    register_user(message)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("Связаться с поддержкой", url="https://t.me/pydev_ai"))
    bot.send_message(message.chat.id, "🛡 Тех. Поддержка всегда готова вам помочь!\nОбращатесь ⏬", reply_markup=kb)


@bot.message_handler(commands=['stats'])
def cmd_stats(message):
    if is_banned(message.from_user.id):
        return

    register_user(message)
    if not is_admin(message.from_user):
        bot.send_message(message.chat.id, "Доступно только администраторам.")
        return
    with _known_lock:
        total_users = len(known_users)
    total_reqs = sum(request_stats.values()) if request_stats else 0
    top = sorted(request_stats.items(), key=lambda kv: kv[1], reverse=True)[:10]
    lines = [f"{users_meta.get(uid, uid)}: {cnt}" for uid, cnt in top]
    bot.send_message(message.chat.id,
                     f"Пользователей: {total_users}\nЗапросов к моделям: {total_reqs}\n\nТоп пользователей:\n" + (
                         "\n".join(lines) if lines else "нет данных"))


@bot.message_handler(commands=['help', 'faq'])
def handle_faq(message):
    register_user(message)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("FAQ", url="https://telegra.ph/FAQ-10-19-23"))
    bot.send_message(message.chat.id, faq, reply_markup=kb)


@bot.message_handler(commands=['ban'])
def cmd_ban(message):
    if not is_admin(message.from_user):
        bot.send_message(message.chat.id, "Доступно только администраторам.")
        return

    try:
        # Получаем аргументы команды
        args = message.text.split()[1:]
        if not args:
            bot.send_message(message.chat.id, "Использование: /ban @username")
            return

        target = args[0]
        target_user_id = None

        # Пытаемся найти user_id
        if target.startswith('@'):
            target_user_id = find_user_id(target)
        else:
            # Если передан числовой ID
            try:
                target_user_id = int(target)
            except ValueError:
                target_user_id = find_user_id('@' + target)

        if not target_user_id:
            bot.send_message(message.chat.id, f"Пользователь {target} не найден.")
            return

        # Баним пользователя
        with _banned_lock:
            banned_users.add(target_user_id)
            save_banned_users(banned_users)

        bot.send_message(message.chat.id, f"✅ Пользователь {target} заблокирован.")
        logger.info(f"Admin {message.from_user.id} banned user {target_user_id}")

    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при блокировке: {e}")
        logger.error(f"Error in ban command: {e}")


@bot.message_handler(commands=['msg'])
def cmd_msg(message):
    if not is_admin(message.from_user):
        bot.send_message(message.chat.id, "Доступно только администраторам.")
        return

    try:
        # Получаем аргументы команды
        args = message.text.split(maxsplit=2)
        if len(args) < 3:
            bot.send_message(message.chat.id, "Использование: /msg @username текст_сообщения")
            return

        target = args[1]
        msg_text = args[2]
        target_user_id = None

        # Пытаемся найти user_id
        if target.startswith('@'):
            target_user_id = find_user_id(target)
        else:
            # Если передан числовой ID
            try:
                target_user_id = int(target)
            except ValueError:
                target_user_id = find_user_id('@' + target)

        if not target_user_id:
            bot.send_message(message.chat.id, f"Пользователь {target} не найден.")
            return

        # Отправляем сообщение
        try:
            bot.send_message(target_user_id, f"📨 Сообщение от администратора:\n\n{msg_text}")
            bot.send_message(message.chat.id, f"✅ Сообщение отправлено пользователю {target}")
            logger.info(f"Admin {message.from_user.id} sent message to user {target_user_id}")
        except Exception as e:
            bot.send_message(message.chat.id,
                             f"❌ Не удалось отправить сообщение пользователю {target}. Возможно, он заблокировал бота.")
            logger.error(f"Error sending message to user {target_user_id}: {e}")

    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при отправке сообщения: {e}")
        logger.error(f"Error in msg command: {e}")


@bot.message_handler(commands=['bc'])
def cmd_bc(message):
    if not is_admin(message.from_user):
        bot.send_message(message.chat.id, "Доступно только администраторам.")
        return

    try:
        # Получаем текст рассылки
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            bot.send_message(message.chat.id, "Использование: /bc текст_рассылки")
            return

        bc_text = args[1]
        sent_count = 0
        failed_count = 0

        bot.send_message(message.chat.id, f"🔄 Начинаю рассылку для {len(known_users)} пользователей...")

        # Рассылаем всем известным пользователям
        for user_id in known_users:
            if is_banned(user_id):
                continue  # Пропускаем заблокированных

            try:
                bot.send_message(user_id, f"📢 Объявление от администратора:\n\n{bc_text}")
                sent_count += 1
                time.sleep(0.1)  # Небольшая задержка чтобы не превысить лимиты Telegram
            except Exception as e:
                failed_count += 1
                logger.warning(f"Failed to send broadcast to {user_id}: {e}")

        bot.send_message(message.chat.id,
                         f"✅ Рассылка завершена!\n"
                         f"📨 Успешно отправлено: {sent_count}\n"
                         f"❌ Не удалось отправить: {failed_count}")

        logger.info(f"Admin {message.from_user.id} sent broadcast to {sent_count} users, failed: {failed_count}")

    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при рассылке: {e}")
        logger.error(f"Error in broadcast command: {e}")


@bot.message_handler(func=lambda m: m.text == "Info 📜")
def on_info(message):
    if is_banned(message.from_user.id):
        return

    register_user(message)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("FAQ", url="https://telegra.ph/FAQ-10-19-23"))
    bot.send_message(message.chat.id, faq, reply_markup=kb)


@bot.message_handler(func=lambda m: m.text == "Channel 👀")
def on_tech_t(message):
    if is_banned(message.from_user.id):
        return

    register_user(message)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("Наш канал", url="https://t.me/ivanisherenow"))
    bot.send_message(message.chat.id, "Наш канал с интересными постами и новостями бота ⏬", reply_markup=kb)


@bot.message_handler(func=lambda m: m.text == "Tech support 🛡")
def on_tech_support(message):
    if is_banned(message.from_user.id):
        return

    register_user(message)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("Связаться с поддержкой", url="https://t.me/pydev_ai"))
    bot.send_message(message.chat.id, "🛡 Тех. Поддержка всегда готова вам помочь!\nОбращатесь ⏬", reply_markup=kb)


@bot.message_handler(commands=['policy'])
def policy_(message):
    if is_banned(message.from_user.id):
        return

    register_user(message)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("Policy", url="https://telegra.ph/Polzovatelskoe-soglashenie-10-19-23"))
    bot.send_message(message.chat.id, policy, reply_markup=kb)


# State flags:
user_in_chat_session: Dict[int, bool] = {}
# Новый флаг: пользователь в web-search режиме
user_web_mode: Dict[int, bool] = {}


def send_message_parts(chat_id: int, text: str, parse_mode: str = "MarkdownV2") -> bool:
    """
    Отправляет сообщение частями используя новый API saver.py
    Возвращает True если отправка успешна, False при ошибке
    """
    try:
        parts = st.send_with_auto_parse(text)
        if not parts:
            bot.send_message(chat_id, "Пустой ответ от модели.")
            return True

        for part in parts:
            try:
                bot.send_message(chat_id, part, parse_mode=parse_mode)
            except Exception as e:
                logger.error(f"Error sending message part: {e}")
                # Попробуем отправить без форматирования
                try:
                    bot.send_message(chat_id, part)
                except Exception:
                    return False
        return True
    except Exception as e:
        logger.error(f"Error in send_message_parts: {e}")
        return False


@bot.message_handler(commands=['web'])
def cmd_web(message):
    """
    Включает режим web search для пользователя.
    """
    if is_banned(message.from_user.id):
        bot.send_message(message.chat.id, "❌ Вы заблокированы и не можете использовать бота.")
        return

    register_user(message)
    uid = message.from_user.id
    user_web_mode[uid] = True
    user_in_chat_session[uid] = True
    bot.send_message(message.chat.id, "🔎 Режим web search включён. Все последующие запросы будут обрабатываться с поиском в интернете.", reply_markup=keyboard_web_mode())
    log_line(message.from_user, "/web", "entered web mode")


@bot.message_handler(func=lambda m: m.text == "Поиск в интернете 🌍")
def on_web_search_button(message):
    """
    Обработка нажатия кнопки 'web search' в главном меню.
    """
    if is_banned(message.from_user.id):
        return

    register_user(message)
    uid = message.from_user.id
    user_web_mode[uid] = True
    user_in_chat_session[uid] = True
    bot.send_message(message.chat.id, "🔎 Режим web search включён. Все последующие запросы будут обрабатываться с поиском в интернете.", reply_markup=keyboard_web_mode())
    log_line(message.from_user, "web search (button)", "entered web mode")


@bot.message_handler(func=lambda m: m.text == "Меню ⏬")
def exit_to_menu(message):
    """
    Выход из web режима (и общий возврат в главное меню).
    """
    uid = message.from_user.id
    if is_banned(uid):
        return

    register_user(message)
    user_web_mode[uid] = False
    user_in_chat_session[uid] = False
    bot.send_message(message.chat.id, "⬅️ Вы возвращены в главное меню.", reply_markup=keyboard_start())
    log_line(message.from_user, "exit web/menu", "returned to menu")


@bot.message_handler(func=lambda m: True, content_types=['text', 'document', 'photo'])
def handle_all_text(message):
    if is_banned(message.from_user.id):
        return

    register_user(message)
    uid = message.from_user.id

    file_was_uploaded = False
    file_path = None
    is_image = False

    # Обработка документов
    if message.document:
        try:
            file_info = bot.get_file(message.document.file_id)
            original_filename = message.document.file_name or "file"
            file_extension = os.path.splitext(original_filename)[1]
            filename = f"doc_{uid}_{int(time.time())}{file_extension}"

            os.makedirs("utils", exist_ok=True)
            file_path = os.path.join("utils", filename)

            downloaded_file = bot.download_file(file_info.file_path)
            with open(file_path, 'wb') as new_file:
                new_file.write(downloaded_file)

            file_was_uploaded = True
            logger.info(f"User {uid} downloaded document: {filename} -> {file_path}")
            bot.send_message(message.chat.id, f"Файл {original_filename} получен. Обрабатываю...")

        except Exception as e:
            logger.error(f"Error downloading document: {e}")
            bot.send_message(message.chat.id, "Ошибка при загрузке файла.")

    # Обработка изображений
    elif message.photo:
        try:
            # Берем фото наибольшего качества (последний в списке)
            photo = message.photo[-1]
            file_info = bot.get_file(photo.file_id)

            file_extension = '.jpg'
            filename = f"photo_{uid}_{int(time.time())}{file_extension}"
            os.makedirs("utils", exist_ok=True)
            file_path = os.path.join("utils", filename)

            downloaded_file = bot.download_file(file_info.file_path)
            with open(file_path, 'wb') as new_file:
                new_file.write(downloaded_file)

            # Нормализуем изображение до 1 МБ
            normalized_path = normalize_image(file_path, 1)
            file_path = normalized_path  # Используем нормализованное изображение

            file_was_uploaded = True
            is_image = True
            logger.info(f"User {uid} uploaded photo: {filename} -> {file_path}")
            bot.send_message(message.chat.id, "📷 Изображение получено. Распознаю текст...")

        except Exception as e:
            logger.error(f"Error downloading photo: {e}")
            bot.send_message(message.chat.id, "Ошибка при загрузке изображения.")

    # ВАЖНО: получаем текст ИЗ ПОДПИСИ К ФАЙЛУ/ИЗОБРАЖЕНИЮ или обычный текст
    text = message.text or message.caption or ""
    logger.info(f"Extracted text: '{text}'")  # Логируем полученный текст

    # ОБРАБОТКА ФАЙЛОВ И ИЗОБРАЖЕНИЙ
    if file_was_uploaded and file_path:
        if not user_in_chat_session.get(uid, False):
            user_in_chat_session[uid] = True

        request_stats[uid] = request_stats.get(uid, 0) + 1

        # Обрабатываем математические выражения в тексте
        inp = st.process_math_expressions(text)
        model = "deepseek"

        logger.info(f"Processing file: {file_path}, text: '{text}', is_image: {is_image}")

        # Если пользователь в web режиме — формируем запрос через prompt_web/query_web,
        # но включаем в текст содержимое файла, используя build_model_prompt
        if user_web_mode.get(uid, False):
            return "Файлы не поддерживаются в web mode :("
        else:
            # Обычный режим без web
            prompt = build_model_prompt(inp, model, file_path)
            logger.info(f"Prompt built, user content length: {len(prompt['user'])}")

            q = query(file_path, prompt['user'], model)
        logger.info(f"Query response length: {len(q) if q else 0}")

        final = st.extract_content(q)
        ok = send_message_parts(message.chat.id, final)

        log_line(message.from_user, f"File: {file_path} | Text: {text}",
                 (final[:800] + ("...[truncated]" if len(final) > 800 else "")))
        return

    if not user_in_chat_session.get(uid, False):
        user_in_chat_session[uid] = True

    if not text.strip():
        return

    request_stats[uid] = request_stats.get(uid, 0) + 1

    processed_input = st.process_math_expressions(text)
    model_choice = "deepseek"

    # Режим web: используем query_web (внутри неё вызывается prompt_web)
    if user_web_mode.get(uid, False):
        try:
            prompt = prompt_web(processed_input)
            raw_resp = query_web(prompt, model_choice)
        except Exception as e:
            logger.exception(f"Error in query_web(): {e}")
            raw_resp = None
    else:
        # Для текстовых запросов передаем None как file_path
        prompt = build_model_prompt(processed_input, model_choice, None)
        try:
            raw_resp = query(None, prompt["user"], model_choice)
        except Exception:
            raw_resp = None

    if not raw_resp:
        bot.send_message(message.chat.id, "Ошибка или пустой ответ от модели.")
        log_line(message.from_user, text, None)
        return

    final = st.extract_content(raw_resp)
    ok = send_message_parts(message.chat.id, final)
    if not ok:
        try:
            bot.send_message(message.chat.id, final)
        except Exception:
            bot.send_message(message.chat.id, "Не удалось отправить сообщение. Попробуйте позже.")

    log_line(message.from_user, text, (final[:800] + ("...[truncated]" if len(final) > 800 else "")))


@bot.inline_handler(lambda q: True)
def handle_inline_query(inline_query):
    try:
        qtext = (inline_query.query or "").strip()

        if not qtext:
            message_text = "Введите запрос после имени бота: @solve_ai_bot <запрос>"
            reply_markup = None
        else:
            # Пытаемся получить ответ от модели, но с коротким таймаутом, чтобы не истекал inline-query
            processed_input = st.process_math_expressions(qtext)
            model_choice = "deepseek"
            prompt = build_model_inline(processed_input, model_choice)

            # Запускаем solver.query в отдельном потоке и даём ему N секунд
            resp_container = {"resp": None, "err": None}
            def call_model():
                try:
                    resp_container["resp"] = query_inline(prompt["user"], model_choice)
                except Exception as e:
                    resp_container["err"] = e

            t = threading.Thread(target=call_model, daemon=True)
            t.start()
            t.join(timeout=10)  # WAIT up to 3 seconds

            if t.is_alive():
                # Модель не ответила быстро — возвращаем подсказку и кнопку "Открыть бота"
                message_text = "Извините — ответ слишком большой или модель отвечает медленно. Откройте бота чтобы увидеть полный ответ."
                reply_markup = types.InlineKeyboardMarkup()
                username_for_url = (BOT_USERNAME).lstrip('@')
                reply_markup.add(types.InlineKeyboardButton(text="Открыть бота", url=f"https://t.me/{username_for_url}"))
            else:
                raw_resp = resp_container.get("resp")
                if not raw_resp:
                    message_text = "Ошибка или пустой ответ от модели."
                    reply_markup = None
                else:
                    # prepare_inline_response вернёт либо единственную часть, либо подсказку + клавиатуру
                    try:
                        # передаём строку username, а не объект bot
                        username_for_prepare = BOT_USERNAME
                        message_text, reply_markup = st.prepare_inline_response(raw_resp, username_for_prepare)
                        message_text = message_text.replace("\\", "")
                    except Exception as e:
                        logger.error(f"prepare_inline_response failed: {e}")
                        message_text = "Ошибка при подготовке ответа."
                        reply_markup = None

        # Создаём InputTextMessageContent **без** parse_mode (plain text) — это предотвращает ошибки парсинга
        input_content = types.InputTextMessageContent(
            message_text=message_text
            # Не указываем parse_mode => Telegram воспримет как plain text
        )

        # Формируем результат
        result = types.InlineQueryResultArticle(
            id=str(time.time_ns()),
            title="Модель ИИ",
            description=(qtext[:50] + ("..." if len(qtext) > 50 else "")) if qtext else "Задайте вопрос",
            input_message_content=input_content,
            reply_markup=reply_markup
        )

        # Отправляем результат (небольшой cache_time)
        bot.answer_inline_query(inline_query.id, [result], cache_time=1, is_personal=True)

    except Exception as e:
        logger.error(f"Error in inline handler: {e}")
        try:
            # Fallback при ошибке - отправляем без parse_mode
            err_content = types.InputTextMessageContent(
                message_text="Произошла ошибка при обработке запроса. Попробуйте позже."
            )
            err_result = types.InlineQueryResultArticle(
                id=str(time.time_ns()),
                title="Ошибка",
                input_message_content=err_content
            )
            bot.answer_inline_query(inline_query.id, [err_result], cache_time=1)
        except Exception as ex:
            logger.error(f"Error in inline error handler: {ex}")


if __name__ == "__main__":
    logger.info("Bot starting...")
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60,
                             allowed_updates=['message', 'edited_message', 'callback_query', 'inline_query',
                                              'chosen_inline_result'])
    except Exception:
        logger.exception("Polling stopped unexpectedly")
        try:
            os._exit(1)
        except Exception:
            sys.exit(1)
