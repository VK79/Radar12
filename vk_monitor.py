"""
VK API мониторинг групп и страниц пользователей
"""
import json
import logging
import time
from typing import List, Dict, Optional, Set, Tuple
from datetime import datetime

try:
    import vk_api
    from vk_api.exceptions import ApiError
except ImportError:
    vk_api = None
    ApiError = Exception

logger = logging.getLogger(__name__)


class VKMonitor:
    """Мониторинг VK групп и страниц пользователей для поиска по ключевым словам"""

    def __init__(self, access_token: str):
        """
        Инициализация VK монитора

        Args:
            access_token: Токен доступа VK API
        """
        if vk_api is None:
            raise ImportError("Библиотека vk_api не установлена. Установите: pip install vk_api")

        self.access_token = access_token
        self.vk_session = None
        self.vk = None
        self.seen_posts: Dict[str, Set[int]] = {}  # entity_id -> set of post_ids
        self._connect()

    def _connect(self):
        """Подключение к VK API"""
        try:
            self.vk_session = vk_api.VkApi(token=self.access_token)
            self.vk = self.vk_session.get_api()
            logger.info("Успешное подключение к VK API")
        except Exception as e:
            logger.error(f"Ошибка подключения к VK API: {e}")
            raise

    def get_entity_info(self, entity_id: str) -> Optional[Dict]:
        """
        Получение информации о сущности (группа или пользователь)

        Определяет тип сущности и возвращает унифицированную информацию.

        Args:
            entity_id: ID или короткое имя группы/пользователя

        Returns:
            Словарь с информацией о сущности или None:
            {
                'id': int,              # ID сущности
                'owner_id': int,        # owner_id для wall.get (с учетом знака)
                'type': 'group'/'user', # Тип сущности
                'name': str,            # Название/имя
                'screen_name': str,     # Короткое имя
                'url': str              # Ссылка на сущность
            }
        """
        # Очищаем входные данные
        entity_id = entity_id.strip().replace('https://vk.com/', '').replace('http://vk.com/', '')
        entity_id = entity_id.strip('/')

        # Сначала пробуем как группу
        group_info = self._try_get_group_info(entity_id)
        if group_info:
            return group_info

        # Если не группа, пробуем как пользователя
        user_info = self._try_get_user_info(entity_id)
        if user_info:
            return user_info

        logger.warning(f"Сущность {entity_id} не найдена (ни группа, ни пользователь)")
        return None

    def _try_get_group_info(self, group_id: str) -> Optional[Dict]:
        """
        Попытка получить информацию о группе

        Args:
            group_id: ID или короткое имя группы

        Returns:
            Информация о группе или None
        """
        try:
            # Определяем, это ID или короткое имя
            try:
                gid = int(group_id)
                # Если передан отрицательный ID, берём модуль
                gid = abs(gid)
                groups = self.vk.groups.getById(group_id=gid)
            except ValueError:
                groups = self.vk.groups.getById(group_id=group_id)

            if groups:
                group = groups[0]
                group_id_val = group.get('id', 0)
                screen_name = group.get('screen_name', f'club{group_id_val}')

                return {
                    'id': group_id_val,
                    'owner_id': -group_id_val,  # Отрицательный ID для групп
                    'type': 'group',
                    'name': group.get('name', 'Неизвестная группа'),
                    'screen_name': screen_name,
                    'url': f"https://vk.com/{screen_name}"
                }
            return None
        except ApiError as e:
            # Группа не найдена - это нормально, возможно это пользователь
            logger.debug(f"Это не группа {group_id}: {e}")
            return None
        except Exception as e:
            logger.debug(f"Ошибка при проверке группы {group_id}: {e}")
            return None

    def _try_get_user_info(self, user_id: str) -> Optional[Dict]:
        """
        Попытка получить информацию о пользователе

        Args:
            user_id: ID или короткое имя пользователя

        Returns:
            Информация о пользователе или None
        """
        try:
            # Определяем, это ID или короткое имя (домен)
            try:
                uid = int(user_id)
                users = self.vk.users.get(user_ids=uid)
            except ValueError:
                users = self.vk.users.get(user_ids=user_id)

            if users:
                user = users[0]
                user_id_val = user.get('id', 0)

                # Формируем полное имя
                first_name = user.get('first_name', '')
                last_name = user.get('last_name', '')
                full_name = f"{first_name} {last_name}".strip() or f"id{user_id_val}"

                # Получаем домен если есть
                domain = user.get('domain', f'id{user_id_val}')

                return {
                    'id': user_id_val,
                    'owner_id': user_id_val,  # Положительный ID для пользователей
                    'type': 'user',
                    'name': full_name,
                    'screen_name': domain,
                    'url': f"https://vk.com/{domain}"
                }
            return None
        except ApiError as e:
            logger.debug(f"Это не пользователь {user_id}: {e}")
            return None
        except Exception as e:
            logger.debug(f"Ошибка при проверке пользователя {user_id}: {e}")
            return None

    def get_wall_posts(self, owner_id: int, count: int = 20) -> List[Dict]:
        """
        Получение постов со стены (группы или пользователя)

        Args:
            owner_id: ID владельца стены (отрицательный для групп, положительный для пользователей)
            count: Количество постов

        Returns:
            Список постов
        """
        try:
            posts = self.vk.wall.get(owner_id=owner_id, count=count)
            return posts.get('items', [])
        except ApiError as e:
            error_msg = str(e)
            if 'access denied' in error_msg.lower() or 'private' in error_msg.lower():
                logger.warning(f"Нет доступа к стене {owner_id} (возможно, приватный профиль)")
            else:
                logger.error(f"Ошибка получения постов стены {owner_id}: {e}")
            return []

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

    def monitor_sources(self, sources: List[str], keywords: List[str],
                        max_posts: int = 20) -> List[Dict]:
        """
        Мониторинг источников (групп и пользователей) на наличие ключевых слов

        Args:
            sources: Список ID или коротких имен групп/пользователей
            keywords: Ключевые слова для поиска
            max_posts: Максимальное количество постов для проверки

        Returns:
            Список найденных совпадений
        """
        all_matches = []

        for source_id in sources:
            try:
                # Получаем информацию о сущности (группа или пользователь)
                entity_info = self.get_entity_info(source_id)
                if not entity_info:
                    logger.warning(f"Источник {source_id} не найден")
                    continue

                entity_type = entity_info['type']
                entity_name = entity_info['name']
                entity_url = entity_info['url']
                owner_id = entity_info['owner_id']
                entity_key = str(abs(owner_id))  # Уникальный ключ для seen_posts

                # Логируем тип источника
                type_label = "Группа" if entity_type == 'group' else "Пользователь"
                logger.info(f"Мониторинг: {type_label} '{entity_name}' (ID: {owner_id})")

                # Инициализируем seen_posts для источника
                if entity_key not in self.seen_posts:
                    self.seen_posts[entity_key] = set()

                # Получаем посты со стены
                posts = self.get_wall_posts(owner_id, max_posts)

                if not posts:
                    logger.debug(f"Нет постов для анализа в источнике {entity_name}")
                    continue

                # Ищем совпадения только в новых постах
                new_matches_count = 0
                for post in posts:
                    post_id = post.get('id')
                    if post_id in self.seen_posts[entity_key]:
                        continue

                    self.seen_posts[entity_key].add(post_id)

                    text = post.get('text', '')
                    found_keywords = self.check_keywords(text, keywords)

                    if found_keywords:
                        new_matches_count += 1
                        all_matches.append({
                            'source': 'vk',
                            'entity_type': entity_type,  # 'group' или 'user'
                            'group_name': entity_name,   # Для совместимости с tg_monitor
                            'group_url': entity_url,
                            'post_id': post_id,
                            'owner_id': owner_id,
                            'text': text[:300] + ('...' if len(text) > 500 else ''),
                            'keywords': found_keywords,
                            'date': datetime.fromtimestamp(post.get('date', 0)).strftime("%d.%m.%Y %H:%M:%S"),
                            'url': f"https://vk.com/wall{owner_id}_{post_id}"
                        })

                if new_matches_count > 0:
                    logger.info(f"Найдено {new_matches_count} новых совпадений в {type_label.lower()} '{entity_name}'")

                # Ограничиваем размер seen_posts
                if len(self.seen_posts[entity_key]) > 1000:
                    self.seen_posts[entity_key] = set(list(self.seen_posts[entity_key])[-500:])

                # Небольшая пауза между запросами
                time.sleep(0.5)

            except Exception as e:
                logger.error(f"Ошибка при мониторинге источника {source_id}: {e}")
                continue

        return all_matches

    # Для обратной совместимости
    def monitor_groups(self, groups: List[str], keywords: List[str],
                       max_posts: int = 20) -> List[Dict]:
        """
        Мониторинг групп на наличие ключевых слов (для обратной совместимости)

        Args:
            groups: Список ID или коротких имен групп/пользователей
            keywords: Ключевые слова для поиска
            max_posts: Максимальное количество постов для проверки

        Returns:
            Список найденных совпадений
        """
        return self.monitor_sources(groups, keywords, max_posts)


if __name__ == "__main__":
    # Тестирование
    import sys
    print("VK Monitor Module - поддерживает группы и страницы пользователей")
    print("Используйте этот модуль через main.py")
    print("\nФорматы источников:")
    print("  - ID группы: '123456' или '-123456'")
    print("  - Короткое имя группы: 'apiclub'")
    print("  - ID пользователя: '123456'")
    print("  - Короткое имя пользователя: 'durov'")
    print("  - Полные ссылки: 'https://vk.com/apiclub'")