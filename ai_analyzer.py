"""
AI анализ текста через OpenRouter API
"""
import aiohttp
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# OpenRouter API endpoint
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"


@dataclass
class AIAnalysisResult:
    """Результат AI-анализа"""
    success: bool
    analysis: Optional[str] = None
    error: Optional[str] = None
    model: Optional[str] = None
    tokens_used: Optional[int] = None


class AIAnalyzer:
    """Анализатор текста через OpenRouter API"""
    
    def __init__(self, api_key: str, model: str = "deepseek/deepseek-r1-0528:free",
                 prompt: str = None):
        """
        Инициализация AI-анализатора
        
        Args:
            api_key: API ключ OpenRouter
            model: Модель для использования
            prompt: Промпт для анализа (по умолчанию - базовый промпт)
        """
        self.api_key = api_key
        self.model = model
        self.prompt = prompt or self._default_prompt()
    
    def _default_prompt(self) -> str:
        """Дефолтный промпт для анализа"""
        return """Ты - аналитик социальных сетей. Проанализируй следующий пост из социальной сети.

Твоя задача:
1. Определи основную тему и смысл поста
2. Оцени тональность (позитивная/негативная/нейтральная)
3. Выдели ключевые тезисы или факты
4. Если есть призыв к действию - укажи какой

Ответь кратко и структурировано (не более 3-4 предложений).

Пост для анализа:
{text}"""
    
    async def analyze(self, text: str, max_length: int = 2000) -> AIAnalysisResult:
        """
        Анализ текста через OpenRouter API
        
        Args:
            text: Текст для анализа
            max_length: Максимальная длина текста для анализа
            
        Returns:
            AIAnalysisResult с результатом анализа
        """
        if not self.api_key:
            return AIAnalysisResult(
                success=False,
                error="OpenRouter API ключ не настроен"
            )
        
        if not text or not text.strip():
            return AIAnalysisResult(
                success=False,
                error="Пустой текст для анализа"
            )
        
        # Обрезаем текст если слишком длинный
        text_to_analyze = text[:max_length]
        if len(text) > max_length:
            text_to_analyze += "..."
        
        # Формируем промпт
        full_prompt = self.prompt.format(text=text_to_analyze)
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/monitor-service",
            "X-Title": "VK-TG-Monitor"
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": full_prompt
                }
            ],
            "max_tokens": 500,
            "temperature": 0.7
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    OPENROUTER_API_URL,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        
                        if "choices" in data and len(data["choices"]) > 0:
                            content = data["choices"][0].get("message", {}).get("content", "")
                            usage = data.get("usage", {})
                            
                            return AIAnalysisResult(
                                success=True,
                                analysis=content.strip(),
                                model=self.model,
                                tokens_used=usage.get("total_tokens", 0)
                            )
                        else:
                            error_msg = data.get("error", {}).get("message", "Неизвестная ошибка")
                            return AIAnalysisResult(
                                success=False,
                                error=f"API ошибка: {error_msg}"
                            )
                    
                    elif response.status == 401:
                        return AIAnalysisResult(
                            success=False,
                            error="Неверный API ключ OpenRouter"
                        )
                    
                    elif response.status == 429:
                        return AIAnalysisResult(
                            success=False,
                            error="Превышен лимит запросов к API"
                        )
                    
                    else:
                        error_text = await response.text()
                        return AIAnalysisResult(
                            success=False,
                            error=f"HTTP ошибка {response.status}: {error_text[:200]}"
                        )
                        
        except aiohttp.ClientTimeout:
            return AIAnalysisResult(
                success=False,
                error="Таймаут запроса к API"
            )
        except aiohttp.ClientError as e:
            return AIAnalysisResult(
                success=False,
                error=f"Ошибка сети: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Неожиданная ошибка AI-анализа: {e}")
            return AIAnalysisResult(
                success=False,
                error=f"Неожиданная ошибка: {str(e)}"
            )
    
    def format_analysis_for_message(self, result: AIAnalysisResult) -> str:
        """
        Форматирование результата для отправки в Telegram
        
        Args:
            result: Результат анализа
            
        Returns:
            Отформатированная строка для сообщения
        """
        if not result.success:
            if result.error:
                return f"\n\n🤖 <b>AI Анализ:</b>\n<i>⚠️ {result.error}</i>"
            return ""
        
        analysis_text = result.analysis or "Не удалось проанализировать"
        
        # Экранируем HTML в анализе
        analysis_text = analysis_text.replace('<', '&lt;').replace('>', '&gt;')
        
        formatted = f"\n\n🤖 <b>AI Анализ:</b>\n{analysis_text}"
        
        if result.model:
            formatted += f"\n\n<i>Модель: {result.model}</i>"
        
        return formatted
    
    def update_settings(self, api_key: str = None, model: str = None, prompt: str = None):
        """
        Обновление настроек анализатора
        
        Args:
            api_key: Новый API ключ
            model: Новая модель
            prompt: Новый промпт
        """
        if api_key is not None:
            self.api_key = api_key
        if model is not None:
            self.model = model
        if prompt is not None:
            self.prompt = prompt if prompt.strip() else self._default_prompt()
        
        logger.info(f"Настройки AI-анализатора обновлены. Модель: {self.model}")


# Глобальный экземпляр анализатора (инициализируется при запуске)
_analyzer: Optional[AIAnalyzer] = None


def get_analyzer() -> Optional[AIAnalyzer]:
    """Получение глобального анализатора"""
    return _analyzer


def init_analyzer(api_key: str, model: str = None, prompt: str = None) -> AIAnalyzer:
    """
    Инициализация глобального анализатора
    
    Args:
        api_key: API ключ OpenRouter
        model: Модель для использования
        prompt: Промпт для анализа
        
    Returns:
        Инициализированный анализатор
    """
    global _analyzer
    
    _analyzer = AIAnalyzer(
        api_key=api_key,
        model=model or "deepseek/deepseek-r1-0528:free",
        prompt=prompt
    )
    
    logger.info(f"AI-анализатор инициализирован. Модель: {_analyzer.model}")
    return _analyzer


async def analyze_text(text: str) -> AIAnalysisResult:
    """
    Удобная функция для анализа текста
    
    Args:
        text: Текст для анализа
        
    Returns:
        Результат анализа
    """
    if _analyzer is None:
        return AIAnalysisResult(
            success=False,
            error="AI-анализатор не инициализирован"
        )
    
    return await _analyzer.analyze(text)


if __name__ == "__main__":
    # Тестирование
    import asyncio
    
    async def test():
        import os
        
        api_key = os.getenv("OPENROUTER_API_KEY", "")
        if not api_key:
            print("Установите OPENROUTER_API_KEY")
            return
        
        analyzer = AIAnalyzer(api_key)
        
        test_text = """
        Важное объявление! Завтра в 15:00 состоится онлайн-встреча 
        по обсуждению нового проекта. Все желающие могут присоединиться 
        по ссылке в описании канала. Обязательно подготовьте вопросы!
        """
        
        print("Анализируем текст...")
        result = await analyzer.analyze(test_text)
        
        print(f"Успех: {result.success}")
        print(f"Анализ: {result.analysis}")
        print(f"Ошибка: {result.error}")
        print(f"Модель: {result.model}")
        
        print("\nФорматированный вывод:")
        print(analyzer.format_analysis_for_message(result))
    
    asyncio.run(test())
