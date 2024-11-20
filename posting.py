import telebot
import vk_api
import os
import logging
from dotenv import load_dotenv
from telebot import types

# Загрузка переменных окружения из файла info.env
load_dotenv('info.env')

# Настройки ВКонтакте
VK_USER_ACCESS_TOKEN = os.getenv("VK_USER_ACCESS_TOKEN")
vk_session = vk_api.VkApi(token=VK_USER_ACCESS_TOKEN)
vk = vk_session.get_api()

# Настройки Telegram
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Словарь для хранения состояния пользователей
user_states = {}

# Загрузка групп из info.env файла
VK_GROUPS = {}
groups_string = os.getenv("VK_GROUPS", "")

# Парсинг строковых данных групп
if groups_string:
    for group in groups_string.split(','):
        group_name, group_id = group.split('=')
        VK_GROUPS[group_name] = int(group_id)

# Функция для отправки изображения в ВКонтакте
def send_photo_to_vk(photo_path: str, group_id: int, message: str = None):
    try:
        upload = vk_api.VkUpload(vk_session)
        photo = upload.photo_wall(photos=photo_path)

        if isinstance(photo, list) and len(photo) > 0:
            attachment = f'photo{photo[0]["owner_id"]}_{photo[0]["id"]}'
            vk.wall.post(
                owner_id=group_id,
                attachments=attachment,
                message=message if message else "",
                from_group=1,
            )
            logger.info(f"Фотография успешно опубликована в группу {group_id}.")
        else:
            logger.error("Ошибка: Не удалось загрузить фотографию.")
            raise ValueError("Не удалось загрузить фотографию.")
    except Exception as e:
        logger.error(f"Ошибка при отправке изображения в ВК: {e}")
        raise

# Обработчик команды /start
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "Привет! Отправьте фото, чтобы опубликовать его в ВК.")

# Обработчик изображений
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    try:
        file_id = message.photo[-1].file_id
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        # Сохраняем изображение
        photo_path = 'postingFrom.png'
        with open(photo_path, 'wb') as new_file:
            new_file.write(downloaded_file)

        # Сохраняем состояние пользователя
        user_states[message.from_user.id] = {'photo_path': photo_path}

        # Создаем клавиатуру
        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        markup.add("Да, добавить текст", "Нет, продолжить так")

        bot.reply_to(
            message,
            "Вы хотите добавить текст к изображению?",
            reply_markup=markup,
        )
    except Exception as e:
        logger.error(f"Ошибка при обработке изображения: {e}")
        bot.reply_to(message, "Произошла ошибка при обработке изображения.")

# Функция для выбора группы
def choose_group(message, caption=None):
    user_state = user_states[message.from_user.id]
    user_state['waiting_for_group'] = True
    user_state['caption'] = caption

    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    for group_name in VK_GROUPS.keys():
        markup.add(group_name)

    bot.reply_to(
        message,
        "Выберите группу, в которую будет опубликован пост:",
        reply_markup=markup,
    )

# Обработчик текстовых сообщений
@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_text(message):
    user_state = user_states.get(message.from_user.id)

    if user_state and 'photo_path' in user_state:
        photo_path = user_state['photo_path']

        if message.text == "Да, добавить текст":
            bot.reply_to(message, "Напишите текст, который вы хотите добавить к изображению.")
            user_state['waiting_for_caption'] = True
        elif message.text == "Нет, продолжить так":
            choose_group(message)
        elif user_state.get('waiting_for_caption'):
            user_state['waiting_for_caption'] = False
            choose_group(message, caption=message.text)
        elif user_state.get('waiting_for_group'):
            group_id = VK_GROUPS.get(message.text)
            if group_id:
                try:
                    send_photo_to_vk(photo_path, group_id, user_state.get('caption'))
                    bot.reply_to(message, f"Фото успешно отправлено в группу {message.text}!")
                    os.remove(photo_path)
                    del user_states[message.from_user.id]
                except Exception as e:
                    logger.error(f"Ошибка при отправке фото в ВК: {e}")
                    bot.reply_to(message, "Ошибка при отправке фото в ВК.")
            else:
                bot.reply_to(message, "Вы выбрали неверную группу. Попробуйте снова.")
                choose_group(message, caption=user_state.get('caption'))
    else:
        bot.reply_to(message, "Отправьте изображение, чтобы продолжить.")

# Запуск бота
while True:
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        logger.error(f"Ошибка в работе бота: {e}")
