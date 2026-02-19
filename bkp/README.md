# Мониторинг VK и Telegram каналов

Система для автоматического мониторинга групп ВКонтакте и каналов Telegram с поиском по ключевым словам и отправкой уведомлений.

## Возможности

- ✅ Мониторинг VK групп
- ✅ Мониторинг Telegram каналов
- ✅ Поиск по ключевым словам
- ✅ Уведомления в Telegram
- ✅ Веб-админка для управления
- ✅ Конфигурация через JSON файл

## Установка

```bash
cd mini-services/monitor
pip install -r requirements.txt
```

## Настройка

### 1. VK API

1. Создайте Standalone-приложение на [vk.com/editapp?act=create](https://vk.com/editapp?act=create)
2. Получите Access Token:
   ```
   https://oauth.vk.com/authorize?client_id=YOUR_APP_ID&display=page&redirect_uri=https://oauth.vk.com/blank.html&scope=groups,wall,offline&response_type=token&v=5.131
   ```
3. Добавьте токен в `config.json` или через админку

### 2. Telegram API

1. Получите API ID и API Hash на [my.telegram.org](https://my.telegram.org)
2. Создайте бота через [@BotFather](https://t.me/BotFather) для отправки уведомлений
3. Добавьте данные в `config.json` или через админку

### 3. Авторизация Telegram

Для мониторинга каналов нужна одноразовая авторизация:

```bash
python main.py --authorize
```

Вам придёт код подтверждения в Telegram, введите его в консоли.

## Запуск

### Полный запуск (мониторинг + админка)

```bash
python main.py
```

### Только админка

```bash
python main.py --admin
# или с указанием порта
python main.py --admin 8080
```

### Только авторизация Telegram

```bash
python main.py --authorize
```

## Админ-панель

После запуска админка доступна по адресу: `http://localhost:5000`

**Данные по умолчанию:**
- Логин: `admin`
- Пароль: `admin123`

> ⚠️ Измените пароль в настройках после первого входа!

## Структура проекта

```
mini-services/monitor/
├── main.py              # Точка входа
├── config.json          # Конфигурация
├── requirements.txt     # Зависимости
├── vk_monitor.py        # Модуль VK
├── tg_monitor.py        # Модуль Telegram
├── admin/               # Веб-админка
│   ├── app.py          # Flask приложение
│   └── templates/      # HTML шаблоны
│       ├── base.html
│       ├── index.html
│       ├── keywords.html
│       ├── recipients.html
│       ├── telegram.html
│       ├── vk.html
│       ├── settings.html
│       └── login.html
└── monitor.log         # Логи
```

## Конфигурация (config.json)

```json
{
  "telegram": {
    "api_id": 12345678,
    "api_hash": "ваш_api_hash",
    "bot_token": "123456789:ABCdef...",
    "phone": "+79991234567",
    "channels": ["@channel1", "https://t.me/channel2"]
  },
  "vk": {
    "access_token": "ваш_access_token",
    "groups": ["group_name", "123456"]
  },
  "keywords": ["слово1", "фраза поиска"],
  "recipients": [123456789, 987654321],
  "admin": {
    "username": "admin",
    "password": "secure_password",
    "secret_key": "случайная_строка"
  },
  "monitoring": {
    "check_interval": 300,
    "max_posts_per_check": 20
  }
}
```

### Параметры

| Параметр | Описание |
|----------|----------|
| `telegram.api_id` | API ID приложения Telegram |
| `telegram.api_hash` | API Hash приложения Telegram |
| `telegram.bot_token` | Токен бота для отправки уведомлений |
| `telegram.phone` | Номер телефона для авторизации |
| `telegram.channels` | Список каналов для мониторинга |
| `vk.access_token` | Access Token VK API |
| `vk.groups` | Список групп для мониторинга |
| `keywords` | Ключевые слова для поиска |
| `recipients` | Chat ID получателей уведомлений |
| `admin.username` | Логин админки |
| `admin.password` | Пароль админки |
| `admin.secret_key` | Секретный ключ Flask |
| `monitoring.check_interval` | Интервал проверки (секунды) |
| `monitoring.max_posts_per_check` | Максимум постов за проверку |

## Как узнать Chat ID

Для добавления получателей уведомлений нужен Chat ID пользователя Telegram:

1. Напишите боту [@userinfobot](https://t.me/userinfobot)
2. Бот ответит вашим Chat ID
3. Добавьте это число в раздел "Получатели"

## Логирование

Все действия записываются в файл `monitor.log`:

```bash
tail -f monitor.log
```

## API Endpoints

| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/api/status` | Статус мониторинга |
| POST | `/api/start` | Запуск мониторинга |
| POST | `/api/stop` | Остановка мониторинга |

## Лицензия

MIT
