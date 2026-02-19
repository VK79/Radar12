"""
VK API мониторинг групп
"""
import json
import logging
import time
from typing import List, Dict, Optional, Set
from datetime import datetime

try:
    import vk_api
    from vk_api.exceptions import ApiError
except ImportError:
    vk_api = None
    ApiError = Exception

logger = logging.getLogger(__name__)


class VKMonitor:
    """Мониторинг VK групп для поиска по ключевым словам"""
    
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
        self.seen_posts: Dict[str, Set[int]] = {}  # group_id -> set of post_ids
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
    
    def get_group_info(self, group_id: str) -> Optional[Dict]:
        """
        Получение информации о группе
        
        Args:
            group_id: ID или короткое имя группы
            
        Returns:
            Информация о группе или None
        """
        try:
            # Определяем, это ID или короткое имя
            try:
                gid = int(group_id)
                groups = self.vk.groups.getById(group_id=gid)
            except ValueError:
                groups = self.vk.groups.getById(group_id=group_id)
            
            if groups:
                return groups[0]
            return None
        except ApiError as e:
            logger.error(f"Ошибка получения информации о группе {group_id}: {e}")
            return None
    
    def get_wall_posts(self, owner_id: int, count: int = 20) -> List[Dict]:
        """
        Получение постов со стены группы
        
        Args:
            owner_id: ID группы (отрицательное число)
            count: Количество постов
            
        Returns:
            Список постов
        """
        try:
            posts = self.vk.wall.get(owner_id=owner_id, count=count)
            return posts.get('items', [])
        except ApiError as e:
            logger.error(f"Ошибка получения постов группы {owner_id}: {e}")
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
    
    def search_in_posts(self, posts: List[Dict], keywords: List[str]) -> List[Dict]:
        """
        Поиск ключевых слов в постах
        
        Args:
            posts: Список постов
            keywords: Ключевые слова для поиска
            
        Returns:
            Список найденных совпадений
        """
        matches = []
        
        for post in posts:
            text = post.get('text', '')
            found_keywords = self.check_keywords(text, keywords)
            
            if found_keywords:
                matches.append({
                    'post_id': post.get('id'),
                    'owner_id': post.get('owner_id'),
                    'text': text[:500] + ('...' if len(text) > 500 else ''),
                    'keywords': found_keywords,
                    'date': datetime.fromtimestamp(post.get('date', 0)).isoformat(),
                    'url': f"https://vk.com/wall{post.get('owner_id')}_{post.get('id')}"
                })
        
        return matches
    
    def monitor_groups(self, groups: List[str], keywords: List[str], 
                       max_posts: int = 20) -> List[Dict]:
        """
        Мониторинг групп на наличие ключевых слов
        
        Args:
            groups: Список ID или коротких имен групп
            keywords: Ключевые слова для поиска
            max_posts: Максимальное количество постов для проверки
            
        Returns:
            Список найденных совпадений
        """
        all_matches = []
        
        for group_id in groups:
            try:
                # Получаем информацию о группе
                group_info = self.get_group_info(group_id)
                if not group_info:
                    logger.warning(f"Группа {group_id} не найдена")
                    continue
                
                group_name = group_info.get('name', group_id)
                group_screen_name = group_info.get('screen_name', group_id)
                owner_id = -group_info.get('id', 0)  # Отрицательный ID для групп
                
                # Инициализируем seen_posts для группы
                group_key = str(abs(owner_id))
                if group_key not in self.seen_posts:
                    self.seen_posts[group_key] = set()
                
                # Получаем посты
                posts = self.get_wall_posts(owner_id, max_posts)
                
                # Ищем совпадения только в новых постах
                for post in posts:
                    post_id = post.get('id')
                    if post_id in self.seen_posts[group_key]:
                        continue
                    
                    self.seen_posts[group_key].add(post_id)
                    
                    text = post.get('text', '')
                    found_keywords = self.check_keywords(text, keywords)
                    
                    if found_keywords:
                        all_matches.append({
                            'source': 'vk',
                            'group_name': group_name,
                            'group_url': f"https://vk.com/{group_screen_name}",
                            'post_id': post_id,
                            'owner_id': owner_id,
                            'text': text[:500] + ('...' if len(text) > 500 else ''),
                            'keywords': found_keywords,
                            'date': datetime.fromtimestamp(post.get('date', 0)).isoformat(),
                            'url': f"https://vk.com/wall{owner_id}_{post_id}"
                        })
                
                # Ограничиваем размер seen_posts
                if len(self.seen_posts[group_key]) > 1000:
                    self.seen_posts[group_key] = set(list(self.seen_posts[group_key])[-500:])
                
                # Небольшая пауза между запросами
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Ошибка при мониторинге группы {group_id}: {e}")
                continue
        
        return all_matches


if __name__ == "__main__":
    # Тестирование
    import sys
    print("VK Monitor Module")
    print("Используйте этот модуль через main.py")
