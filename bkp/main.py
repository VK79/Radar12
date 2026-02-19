#!/usr/bin/env python3
"""
Основной модуль мониторинга VK и Telegram
"""
import json
import os
import asyncio
import logging
import threading
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('monitor.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Путь к конфигурации
CONFIG_PATH = Path(__file__).parent / 'config.json'


class ConfigManager:
    """Менеджер конфигурации"""
    
    def __init__(self, config_path: Path = CONFIG_PATH):
        self.config_path = config_path
        self._lock = threading.Lock()
        self._config: Optional[Dict] = None
    
    def load(self) -> Dict:
        """Загрузка конфигурации"""
        with self._lock:
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
                return self._config
            except FileNotFoundError:
                logger.warning(f"Конфигурационный файл не найден: {self.config_path}")
                return self._create_default()
            except json.JSONDecodeError as e:
                logger.error(f"Ошибка парсинга конфигурации: {e}")
                return self._create_default()
    
    def _create_default(self) -> Dict:
        """Создание конфигурации по умолчанию"""
        default = {
            "telegram": {
                "api_id": 0,
                "api_hash": "",
                "bot_token": "",
                "phone": "",
                "channels": []
            },
            "vk": {
                "access_token": "",
                "groups": []
            },
            "keywords": [],
            "recipients": [],
            "admin": {
                "username": "admin",
                "password": "admin123",
                "secret_key": "change-this-secret-key-in-production"
            },
            "monitoring": {
                "check_interval": 300,
                "max_posts_per_check": 20
            }
        }
        self.save(default)
        return default
    
    def save(self, config: Dict):
        """Сохранение конфигурации"""
        with self._lock:
            try:
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, ensure_ascii=False, indent=2)
                self._config = config
                logger.info("Конфигурация сохранена")
            except Exception as e:
                logger.error(f"Ошибка сохранения конфигурации: {e}")
    
    def get(self) -> Dict:
        """Получение текущей конфигурации"""
        if self._config is None:
            return self.load()
        return self._config
    
    def update(self, updates: Dict):
        """Обновление конфигурации"""
        config = self.get()
        config.update(updates)
        self.save(config)
    
    # Управление ключевыми словами
    def add_keyword(self, keyword: str) -> bool:
        """Добавление ключевого слова"""
        config = self.get()
        if keyword.lower() not in [k.lower() for k in config.get('keywords', [])]:
            config.setdefault('keywords', []).append(keyword)
            self.save(config)
            return True
        return False
    
    def remove_keyword(self, keyword: str) -> bool:
        """Удаление ключевого слова"""
        config = self.get()
        keywords = config.get('keywords', [])
        for i, k in enumerate(keywords):
            if k.lower() == keyword.lower():
                keywords.pop(i)
                self.save(config)
                return True
        return False
    
    def get_keywords(self) -> List[str]:
        """Получение списка ключевых слов"""
        return self.get().get('keywords', [])
    
    # Управление получателями
    def add_recipient(self, chat_id: int) -> bool:
        """Добавление получателя"""
        config = self.get()
        recipients = config.get('recipients', [])
        if chat_id not in recipients:
            recipients.append(chat_id)
            self.save(config)
            return True
        return False
    
    def remove_recipient(self, chat_id: int) -> bool:
        """Удаление получателя"""
        config = self.get()
        recipients = config.get('recipients', [])
        if chat_id in recipients:
            recipients.remove(chat_id)
            self.save(config)
            return True
        return False
    
    def get_recipients(self) -> List[int]:
        """Получение списка получателей"""
        return self.get().get('recipients', [])
    
    # Управление Telegram каналами
    def add_telegram_channel(self, channel: str) -> bool:
        """Добавление Telegram канала"""
        config = self.get()
        channels = config.setdefault('telegram', {}).setdefault('channels', [])
        if channel not in channels:
            channels.append(channel)
            self.save(config)
            return True
        return False
    
    def remove_telegram_channel(self, channel: str) -> bool:
        """Удаление Telegram канала"""
        config = self.get()
        channels = config.setdefault('telegram', {}).setdefault('channels', [])
        if channel in channels:
            channels.remove(channel)
            self.save(config)
            return True
        return False
    
    def get_telegram_channels(self) -> List[str]:
        """Получение списка Telegram каналов"""
        return self.get().get('telegram', {}).get('channels', [])
    
    # Управление VK группами
    def add_vk_group(self, group: str) -> bool:
        """Добавление VK группы"""
        config = self.get()
        groups = config.setdefault('vk', {}).setdefault('groups', [])
        if group not in groups:
            groups.append(group)
            self.save(config)
            return True
        return False
    
    def remove_vk_group(self, group: str) -> bool:
        """Удаление VK группы"""
        config = self.get()
        groups = config.setdefault('vk', {}).setdefault('groups', [])
        if group in groups:
            groups.remove(group)
            self.save(config)
            return True
        return False
    
    def get_vk_groups(self) -> List[str]:
        """Получение списка VK групп"""
        return self.get().get('vk', {}).get('groups', [])


class MonitorService:
    """Основной сервис мониторинга"""
    
    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager
        self.vk_monitor = None
        self.tg_monitor = None
        self.tg_notifier = None
        self.running = False
        self._monitor_task = None
    
    def _init_vk_monitor(self):
        """Инициализация VK монитора"""
        try:
            from vk_monitor import VKMonitor
            config = self.config.get()
            token = config.get('vk', {}).get('access_token', '')
            if token:
                self.vk_monitor = VKMonitor(token)
                logger.info("VK монитор инициализирован")
            else:
                logger.warning("VK токен не настроен")
        except ImportError as e:
            logger.warning(f"VK монитор недоступен: {e}")
        except Exception as e:
            logger.error(f"Ошибка инициализации VK монитора: {e}")
    
    async def _init_tg_monitor(self):
        """Инициализация Telegram монитора"""
        try:
            from tg_monitor import TelegramMonitor, TelegramNotifier
            config = self.config.get()
            tg_config = config.get('telegram', {})
            
            api_id = tg_config.get('api_id', 0)
            api_hash = tg_config.get('api_hash', '')
            phone = tg_config.get('phone', '')
            bot_token = tg_config.get('bot_token', '')
            
            if api_id and api_hash:
                self.tg_monitor = TelegramMonitor(api_id, api_hash, phone)
                await self.tg_monitor.connect()
                logger.info("Telegram монитор инициализирован")
            
            if bot_token:
                self.tg_notifier = TelegramNotifier(bot_token)
                logger.info("Telegram нотификатор инициализирован")
            
        except ImportError as e:
            logger.warning(f"Telegram монитор недоступен: {e}")
        except Exception as e:
            logger.error(f"Ошибка инициализации Telegram монитора: {e}")
    
    async def _monitor_cycle(self):
        """Один цикл мониторинга"""
        config = self.config.get()
        keywords = config.get('keywords', [])
        
        if not keywords:
            logger.debug("Нет ключевых слов для поиска")
            return
        
        max_posts = config.get('monitoring', {}).get('max_posts_per_check', 20)
        all_matches = []
        
        # VK мониторинг
        if self.vk_monitor:
            vk_groups = config.get('vk', {}).get('groups', [])
            if vk_groups:
                logger.info(f"Проверка {len(vk_groups)} VK групп...")
                try:
                    vk_matches = self.vk_monitor.monitor_groups(vk_groups, keywords, max_posts)
                    all_matches.extend(vk_matches)
                    logger.info(f"Найдено {len(vk_matches)} совпадений в VK")
                except Exception as e:
                    logger.error(f"Ошибка VK мониторинга: {e}")
        
        # Telegram мониторинг
        if self.tg_monitor and self.tg_monitor._connected:
            tg_channels = config.get('telegram', {}).get('channels', [])
            if tg_channels:
                logger.info(f"Проверка {len(tg_channels)} Telegram каналов...")
                try:
                    tg_matches = await self.tg_monitor.monitor_channels(tg_channels, keywords, max_posts)
                    all_matches.extend(tg_matches)
                    logger.info(f"Найдено {len(tg_matches)} совпадений в Telegram")
                except Exception as e:
                    logger.error(f"Ошибка Telegram мониторинга: {e}")
        
        # Отправка уведомлений
        if all_matches and self.tg_notifier:
            recipients = config.get('recipients', [])
            if recipients:
                for match in all_matches:
                    try:
                        await self.tg_notifier.notify_recipients(recipients, match)
                        logger.info(f"Уведомление отправлено {len(recipients)} получателям")
                    except Exception as e:
                        logger.error(f"Ошибка отправки уведомления: {e}")
    
    async def _run_monitoring(self):
        """Основной цикл мониторинга"""
        self._init_vk_monitor()
        await self._init_tg_monitor()
        
        config = self.config.get()
        interval = config.get('monitoring', {}).get('check_interval', 300)
        
        logger.info(f"Мониторинг запущен. Интервал проверки: {interval} сек.")
        
        while self.running:
            try:
                await self._monitor_cycle()
            except Exception as e:
                logger.error(f"Ошибка в цикле мониторинга: {e}")
            
            # Ждем с возможностью прерывания
            for _ in range(interval):
                if not self.running:
                    break
                await asyncio.sleep(1)
        
        # Очистка
        if self.tg_monitor:
            await self.tg_monitor.disconnect()
        
        logger.info("Мониторинг остановлен")
    
    def start(self):
        """Запуск мониторинга"""
        if self.running:
            return
        
        self.running = True
        
        def run_async():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._run_monitoring())
        
        thread = threading.Thread(target=run_async, daemon=True)
        thread.start()
        logger.info("Поток мониторинга запущен")
    
    def stop(self):
        """Остановка мониторинга"""
        self.running = False
        logger.info("Остановка мониторинга...")
    
    def is_running(self) -> bool:
        """Проверка, запущен ли мониторинг"""
        return self.running


# Глобальные экземпляры
config_manager = ConfigManager()
monitor_service = MonitorService(config_manager)


if __name__ == "__main__":
    import sys
    
    print("=" * 50)
    print("Мониторинг VK и Telegram")
    print("=" * 50)
    
    # Проверка аргументов
    if len(sys.argv) > 1:
        if sys.argv[1] == "--authorize":
            # Авторизация в Telegram
            from tg_monitor import authorize_telegram
            
            config = config_manager.load()
            tg_config = config.get('telegram', {})
            
            asyncio.run(authorize_telegram(
                tg_config.get('api_id', 0),
                tg_config.get('api_hash', ''),
                tg_config.get('phone', '')
            ))
            sys.exit(0)
        
        elif sys.argv[1] == "--admin":
            # Запуск админки
            from admin.app import run_admin
            
            config = config_manager.load()
            port = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
            run_admin(port=port)
            sys.exit(0)
    
    # Обычный запуск - мониторинг + админка
    print("\nЗапуск мониторинга...")
    monitor_service.start()
    
    print("\nЗапуск админки...")
    from admin.app import run_admin
    run_admin(port=5000)
