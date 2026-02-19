#!/usr/bin/env python3
"""
Тест авторизации Telegram
"""
import asyncio
import json
from pathlib import Path


async def test_telegram_auth():
    # Загружаем конфиг
    config_path = Path(__file__).parent / 'config.json'
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    tg_config = config.get('telegram', {})
    api_id = tg_config.get('api_id', 0)
    api_hash = tg_config.get('api_hash', '')

    if not api_id or not api_hash:
        print("❌ Ошибка: api_id или api_hash не настроены в config.json")
        return False

    print(f"API ID: {api_id}")
    print(f"API Hash: {api_hash[:8]}...")

    from telethon import TelegramClient

    # Пробуем разные имена сессий
    session_names = ['auth_session', 'auth_session', 'test_session']

    for session_name in session_names:
        session_file = Path(f"{session_name}.session")
        print(f"\n📂 Проверка сессии: {session_name}")

        client = TelegramClient(session_name, api_id, api_hash)

        try:
            await client.connect()

            if await client.is_user_authorized():
                me = await client.get_me()
                print(f"✅ Авторизован как: {me.first_name} {me.last_name or ''}")
                print(f"   Телефон: {me.phone}")
                print(f"   ID: {me.id}")

                # Тестируем получение канала
                try:
                    entity = await client.get_entity('@marireporter')
                    print(f"\n✅ Канал найден: {entity.title}")
                except Exception as e:
                    print(f"\n⚠️ Ошибка получения канала: {e}")

                await client.disconnect()
                return True
            else:
                print(f"❌ Сессия {session_name} не авторизована")
                await client.disconnect()

        except Exception as e:
            print(f"❌ Ошибка: {e}")

    print("\n" + "=" * 50)
    print("ТРЕБУЕТСЯ АВТОРИЗАЦИЯ!")
    print("=" * 50)
    print("\nЗапустите команду:")
    print("  python main.py --authorize")
    print("\nИли используйте скрипт авторизации ниже:")

    return False


async def authorize():
    """Интерактивная авторизация"""
    config_path = Path(__file__).parent / 'config.json'
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    tg_config = config.get('telegram', {})
    api_id = tg_config.get('api_id', 0)
    api_hash = tg_config.get('api_hash', '')
    phone = tg_config.get('phone', '')

    if not api_id or not api_hash:
        print("❌ Сначала укажите api_id и api_hash в config.json")
        return

    if not phone:
        phone = input("Введите номер телефона (с +): ").strip()

    from telethon import TelegramClient

    client = TelegramClient('auth_session', api_id, api_hash)
    await client.connect()

    if not await client.is_user_authorized():
        print(f"\nОтправка кода на {phone}...")
        await client.send_code_request(phone)

        code = input("Введите код из Telegram: ").strip()

        try:
            await client.sign_in(phone, code)
            print("\n✅ Авторизация успешна!")
        except Exception as e:
            if "password" in str(e).lower():
                password = input("Введите пароль 2FA: ").strip()
                await client.sign_in(password=password)
                print("\n✅ Авторизация успешна!")
            else:
                print(f"❌ Ошибка: {e}")

    me = await client.get_me()
    print(f"\nВы авторизованы как: {me.first_name} (ID: {me.id})")

    await client.disconnect()


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == '--auth':
        asyncio.run(authorize())
    else:
        asyncio.run(test_telegram_auth())