ERROR_GENERIC = "**Помилка**"
ERROR_NOT_APPOLO = f"{ERROR_GENERIC}: повідомлення не від Apollo бота"
SYNCED = "Команди синхронізовані"
ERROR_WRONG_URL = f"{ERROR_GENERIC}: надане посилання не виглядає правильним"
ERROR_MESSAGE_NOT_FOUND = f"{ERROR_GENERIC}: повідомлення не знайдено за посиланням"
ERROR_NO_PERMISSION = f"{ERROR_GENERIC}: я не маю доступу до"
ERROR_MESSAGE_LINK_CANNOT_BE_RESOLVED = f"{ERROR_GENERIC}: повідомлення не знайдено. Вкажіть посилання на повідомлення або використовуйте в каналі з"
ERROR_NOT_READY = f'{ERROR_GENERIC}: Команда в розробці та не готова до використання'

MISSING_MENTIONS_COMMAND_DESCRIPTION = "Повертає теги мемберів ролі які не проставили реакцію на подію Apollo бота"
MISSING_MENTIONS_MESSAGE_LINK_DESCRIPTION = "Посилання на повідомлення від Apollo. Пусте - пошук повідомлення від Apollo"
MISSING_MENTIONS_ROLE_DESCRIPTION = "Тег ролі, мемберів якої перевіряємо на проставлені реакції"
MISSING_MENTIONS_ERROR_NO_MEMBERS = f"{ERROR_GENERIC}: вказана роль не містить ні одного користувача"
MISSING_MENTIONS_MEMBERS_ALL_REACTED = "Всі мембери ролі проставили реакцію на подію"
MISSING_MENTIONS_RESPONSE_SUCCESS = "- відсутні реакції від"
MISSING_MENTIONS_CANNOT_FIND_APOLLO_MESSAGE = "повідомленням про івент від Apollo"
MISSING_MENTIONS_ADDITIONAL_ROLE_DESCRIPTION = "(Додаткова роль)"

MISSING_VOICE_COMMAND_DESCRIPTION = "Повертає теги мемберів з повідомлення які не зайшли у вказаний голосовий канал"
MISSING_VOICE_MESSAGE_LINK_DESCRIPTION = "Посилання на повідомлення. Пусте - пошук повідомлення з ~ на початку"
MISSING_VOICE_CHANNEL_NAME_DESCRIPTION = "Ім'я голосового каналу з яким порівнюється список мемберів"
MISSING_VOICE_ERROR_NO_MEMBERS = f"{ERROR_GENERIC}: Надане повідомлення не містить ні одного тегу користувачів"
MISSING_VOICE_ERROR_NO_CHANNEL_MATCHES = f"{ERROR_GENERIC}: Не знайдено ні одного голосового каналу, який відповідає вашому запиту"
MISSING_VOICE_MULTIPLE_MATCHES_FIRST = "Знайдено декілька голосових каналів за вашим запитом"
MISSING_VOICE_MULTIPLE_MATCHES_SECOND = "Будь-ласка виберіть один за допомогою кнопок"
MISSING_VOICE_ALL_PRESENT = "Всі мембери з повідомлення вже присутні у голосовому каналі"
MISSING_VOICE_RESPONSE_SUCCESS = "- у цьому голосовому каналі відсутні"
MISSING_VOICE_CANCEL_MULTIPLE_SELECT = "Операція відмінена"
MISSING_VOICE_CANCEL_LABEL = "Відміна"
MISSING_VOICE_TIMEOUT = "Час здійснення операції витік"
MISSING_VOICE_SELECTED_CHANNEL = "Вибрано канал"
MISSING_VOICE_EXACT_MATCH_CHANNEL = "Знайдено канал"
MISSING_VOICE_CANNOT_FIND_MESSAGE = "повідомленням яке починається на тільду ~"

GENERATE_ROSTER_COMMAND_DESCRIPTION = "Генерує склад з тексту. Перетворює назви ролей та кольорів у іконки, та імена у теги"
GENERATE_ROSTER_PARAMETER_DESCRIPTION = "Посилання на повідомлення з ростером для генерації"
GENERATE_ROSTER_SUCCESS = "Згенерований склад"
GENERATE_ROSTER_FAILED = "Не вдалося згенерувати склад з тексту"

PING_TENTATIVE_COMMAND_DESCRIPTION = 'Повертає теги мемберів які проставили "Під питанням" реакцію на подію Apollo бота'
PING_TENTATIVE_MESSAGE_LINK_DESCRIPTION = "Посилання на повідомлення від Apollo. Пусте - пошук повідомлення від Apollo"
PING_TENTATIVE_RESPONSE_SUCCESS = 'Будь-ласка, оновіть ваші ❔"Під питанням" реакції'
PING_TENTATIVE_MENTIONS_MEMBERS_ALL_REACTED = '❔"Під питанням" реакції відсутні'