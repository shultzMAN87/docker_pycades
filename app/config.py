"""Настройки сервиса. Всё чувствительное берётся из переменных окружения."""

from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Отпечаток (SHA-1) сертификата, которым подписываем по умолчанию.
    # Если не задан — берётся первый сертификат с закрытым ключом.
    cert_thumbprint: Optional[str] = None

    # Пин-код контейнера закрытого ключа.
    cert_pin: Optional[str] = None

    # Проверять сертификат перед подписью (цепочка, срок действия, отзыв).
    # Для тестовых и просроченных сертификатов должно быть False.
    check_certificate: bool = False

    # Форматировать подпись переносами строк (base64 в столбик).
    formatted_signature: bool = True


settings = Settings()
