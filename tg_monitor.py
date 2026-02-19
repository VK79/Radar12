"""
Telegram мониторинг каналов через Telethon
"""
import json
import logging
import asyncio
from typing import List, Dict, Optional, Set
from datetime import datetime

try:
    from telethon import TelegramClient, errors
    from telethon.tl.types import Channel, Chat
    from telethon.tl.functions.channels import GetFullChannelRequest
except ImportError:
    TelegramClient = None
    errors = None

logger = logging.getLogger(__name__)


class TelegramMonitor:
    """Мониторинг Telegram каналов для поиска по ключевым словам"""
    
    def __init__(self, api_id: int, api_hash: str, phone: str = None,
                 session_name: str = "auth_session"):
        """
        Инициализация Telegram монитора
        
        Args:
            api_id: API ID приложения Telegram
            api_hash: API Hash приложения Telegram
            phone: Номер телефона (для авторизации)
            session_name: Имя файла сессии
        """
        if TelegramClient is None:
            raise ImportError("Библиотека telethon не установлена. Установите: pip install telethon")
        
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.session_name = session_name
        self.client: Optional[TelegramClient] = None
        self.seen_messages: Dict[str, Set[int]] = {}  # channel_id -> set of message_ids
        self._connected = False
    
    async def connect(self):
        """Асинхронное подключение к Telegram"""
        try:
            self.client = TelegramClient(self.session_name, self.api_id, self.api_hash)
            await self.client.connect()
            
            if not await self.client.is_user_authorized():
                if self.phone:
                    logger.info(f"Отправка кода подтверждения на {self.phone}")
                    await self.client.send_code_request(self.phone)
                    logger.info("Код отправлен. Запустите скрипт авторизации для ввода кода.")
                else:
                    logger.error("Требуется авторизация. Укажите номер телефона.")
                    return False
            
            self._connected = True
            logger.info("Успешное подключение к Telegram")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка подключения к Telegram: {e}")
            return False
    
    async def disconnect(self):
        """Отключение от Telegram"""
        if self.client:
            await self.client.disconnect()
            self._connected = False
            logger.info("Отключено от Telegram")
    
    async def get_channel_info(self, channel_link: str) -> Optional[Dict]:
        """
        Получение информации о канале
        
        Args:
            channel_link: Ссылка на канал или username
            
        Returns:
            Информация о канале или None
        """
        try:
            # Очищаем ссылку
            channel_link = channel_link.replace('https://t.me/', '@').replace('http://t.me/', '@')
            if not channel_link.startswith('@'):
                channel_link = '@' + channel_link
            
            entity = await self.client.get_entity(channel_link)
            
            if isinstance(entity, Channel):
                return {
                    'id': entity.id,
                    'title': entity.title,
                    'username': entity.username,
                    'link': f"https://t.me/{entity.username}" if entity.username else None
                }
            elif isinstance(entity, Chat):
                return {
                    'id': entity.id,
                    'title': entity.title,
                    'username': None,
                    'link': None
                }
            return None
            
        except Exception as e:
            logger.error(f"Ошибка получения информации о канале {channel_link}: {e}")
            return None
    
    def check_keywords(self, text: str, keywords: List[str]) -> List[str]:
        """
        Проверка текста на наличие ключевых слов
        
        Args:
            text: Текст для проверки
            keywords: Список ключевых слов
            
        Returns:
            Список найденных ключевых слов
        """
        if not text:
            return []
        
        text_lower = text.lower()
        found = []
        
        for keyword in keywords:
            if keyword.lower() in text_lower:
                found.append(keyword)
        
        return found
    
    async def get_recent_messages(self, channel_link: str, limit: int = 20) -> List[Dict]:
        """
        Получение последних сообщений из канала
        
        Args:
            channel_link: Ссылка на канал
            limit: Количество сообщений
            
        Returns:
            Список сообщений
        """
        try:
            # Очищаем ссылку
            channel_link = channel_link.replace('https://t.me/', '@').replace('http://t.me/', '@')
            if not channel_link.startswith('@'):
                channel_link = '@' + channel_link
            
            entity = await self.client.get_entity(channel_link)
            messages = await self.client.get_messages(entity, limit=limit)
            
            result = []
            for msg in messages:
                if msg.text:
                    result.append({
                        'id': msg.id,
                        'text': msg.text,
                        'date': msg.date.isoformat() if msg.date else None
                    })
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка получения сообщений из канала {channel_link}: {e}")
            return []
    
    async def monitor_channels(self, channels: List[str], keywords: List[str],
                                limit: int = 20) -> List[Dict]:
        """
        Мониторинг каналов на наличие ключевых слов
        
        Args:
            channels: Список ссылок на каналы
            keywords: Ключевые слова для поиска
            limit: Количество сообщений для проверки
            
        Returns:
            Список найденных совпадений
        """
        if not self._connected:
            logger.error("Не подключено к Telegram")
            return []
        
        all_matches = []
        
        for channel_link in channels:
            try:
                # Получаем информацию о канале
                channel_info = await self.get_channel_info(channel_link)
                if not channel_info:
                    logger.warning(f"Канал {channel_link} не найден")
                    continue
                
                channel_id = str(channel_info['id'])
                channel_name = channel_info['title']
                channel_url = channel_info['link'] or channel_link
                
                # Инициализируем seen_messages для канала
                if channel_id not in self.seen_messages:
                    self.seen_messages[channel_id] = set()
                
                # Получаем сообщения
                messages = await self.get_recent_messages(channel_link, limit)
                
                # Ищем совпадения только в новых сообщениях
                for msg in messages:
                    msg_id = msg['id']
                    if msg_id in self.seen_messages[channel_id]:
                        continue
                    
                    self.seen_messages[channel_id].add(msg_id)
                    
                    text = msg['text']
                    found_keywords = self.check_keywords(text, keywords)
                    
                    if found_keywords:
                        all_matches.append({
                            'source': 'telegram',
                            'channel_name': channel_name,
                            'channel_url': channel_url,
                            'message_id': msg_id,
                            'text': text[:500] + ('...' if len(text) > 500 else ''),
                            'keywords': found_keywords,
                            'date': msg['date'],
                            'url': f"{channel_url}/{msg_id}" if channel_url else None
                        })
                
                # Ограничиваем размер seen_messages
                if len(self.seen_messages[channel_id]) > 1000:
                    self.seen_messages[channel_id] = set(list(self.seen_messages[channel_id])[-500:])
                
                # Небольшая пауза между запросами
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Ошибка при мониторинге канала {channel_link}: {e}")
                continue
        
        return all_matches


class TelegramNotifier:
    """Отправка уведомлений через Telegram бота"""
    
    def __init__(self, bot_token: str):
        """
        Инициализация нотификатора
        
        Args:
            bot_token: Токен Telegram бота
        """
        self.bot_token = bot_token
        self.api_url = f"https://api.telegram.org/bot{bot_token}"
    
    async def send_message(self, chat_id: int, text: str, 
                           parse_mode: str = "HTML") -> bool:
        """
        Отправка сообщения
        
        Args:
            chat_id: ID чата
            text: Текст сообщения
            parse_mode: Режим форматирования
            
        Returns:
            True если успешно
        """
        import aiohttp
        
        url = f"{self.api_url}/sendMessage"
        data = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': parse_mode,
            'disable_web_page_preview': True
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data) as response:
                    if response.status == 200:
                        return True
                    else:
                        error = await response.text()
                        logger.error(f"Ошибка отправки сообщения: {error}")
                        return False
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения: {e}")
            return False
    
    def format_match_message(self, match: Dict, ai_result=None) -> str:
        """
        Форматирование сообщения о совпадении
        
        Args:
            match: Информация о совпадении
            ai_result: Результат AI-анализа (опционально)
            
        Returns:
            Отформатированное сообщение
        """
        source = match.get('source', 'unknown')
        keywords = ', '.join(match.get('keywords', []))
        
        # Формируем AI-часть сообщения
        ai_text = ""
        if ai_result and ai_result.success:
            analysis = ai_result.analysis or ""
            # Экранируем HTML
            analysis = analysis.replace('<', '&lt;').replace('>', '&gt;')
            ai_text = f"\n\n🤖 <b>AI Анализ:</b>\n{analysis}"
        elif ai_result and ai_result.error:
            ai_text = f"\n\n🤖 <b>AI Анализ:</b>\n<i>⚠️ {ai_result.error}</i>"
        
        if source == 'telegram':
            channel = match.get('channel_name', 'Неизвестный канал')
            url = match.get('url', '')
            text = match.get('text', '')
            date = match.get('date', '')
            
            message = f"""🔔 <b>Найдено совпадение в Telegram!</b>

📢 <b>Канал:</b> {channel}
🔑 <b>Ключевые слова:</b> {keywords}
📅 <b>Дата:</b> {date}

📝 <b>Текст:</b>
<code>{text[:300]}{'...' if len(text) > 300 else ''}</code>{ai_text}

🔗 <a href="{url}">Ссылка на сообщение</a>"""
        
        elif source == 'vk':
            group = match.get('group_name', 'Неизвестная группа')
            url = match.get('url', '')
            text = match.get('text', '')
            date = match.get('date', '')
            
            message = f"""🔔 <b>Найдено совпадение в VK!</b>

👥 <b>Группа:</b> {group}
🔑 <b>Ключевые слова:</b> {keywords}
📅 <b>Дата:</b> {date}

📝 <b>Текст:</b>
<code>{text[:300]}{'...' if len(text) > 300 else ''}</code>{ai_text}

🔗 <a href="{url}">Ссылка на пост</a>"""
        
        else:
            message = f"""🔔 <b>Найдено совпадение!</b>

🔑 <b>Ключевые слова:</b> {keywords}
📝 <b>Текст:</b> {match.get('text', '')[:300]}{ai_text}"""
        
        return message
    
    async def notify_recipients(self, recipients: List[int], match: Dict, ai_result=None):
        """
        Отправка уведомления всем получателям
        
        Args:
            recipients: Список ID получателей
            match: Информация о совпадении
            ai_result: Результат AI-анализа (опционально)
        """
        message = self.format_match_message(match, ai_result)
        
        for chat_id in recipients:
            await self.send_message(chat_id, message)
            await asyncio.sleep(0.1)  # Небольшая пауза между отправками


async def authorize_telegram(api_id: int, api_hash: str, phone: str):
    """
    Авторизация в Telegram (выполнить один раз)
    
    Args:
        api_id: API ID
        api_hash: API Hash
        phone: Номер телефона
    """
    client = TelegramClient('auth_session', api_id, api_hash)
    await client.connect()
    
    if not await client.is_user_authorized():
        await client.send_code_request(phone)
        code = input("Введите код подтверждения: ")
        await client.sign_in(phone, code)
        print("Авторизация успешна!")
    else:
        print("Уже авторизованы")
    
    await client.disconnect()


if __name__ == "__main__":
    print("Telegram Monitor Module")
    print("Используйте этот модуль через main.py")
