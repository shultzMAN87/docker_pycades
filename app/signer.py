"""Тонкий сервисный слой между FastAPI и обёрткой pycades."""

from typing import List, Optional, Union

from config import settings
from vendor.cryptopro import Certificate, CryptoPro


class SignerError(RuntimeError):
    """Ошибка уровня подписи (сертификат не найден, неверный пин и т.п.)."""


def _open() -> CryptoPro:
    try:
        return CryptoPro()
    except Exception as exc:  # noqa: BLE001
        raise SignerError(f"не удалось открыть хранилище сертификатов: {exc}") from exc


def module_version() -> str:
    """Версия расширения pycades."""
    return CryptoPro.module_version()


def list_certificates() -> List[dict]:
    """Все сертификаты с закрытым ключом, доступные из ключевых контейнеров."""
    result = []
    for cert in _open().certs.all():
        result.append(
            {
                "thumbprint": cert.thumbprint,
                "subject": cert.info.subject_simple_name,
                "issuer": cert.info.issuer_simple_name,
                "serial_number": cert.serial_number,
                "valid_from": cert.valid_from_date.isoformat(),
                "valid_to": cert.valid_to_date.isoformat(),
                "has_private_key": cert.has_private_key,
                "is_valid": cert.is_valid,
                "container": cert.private_key.container_name if cert.has_private_key else None,
            }
        )
    return result


def get_certificate(thumbprint: Optional[str] = None) -> Certificate:
    """
    Возвращает сертификат по отпечатку.
    Если отпечаток не передан — берётся CERT_THUMBPRINT из окружения,
    а если и его нет — первый доступный сертификат.
    """
    crypto_pro = _open()
    thumbprint = thumbprint or settings.cert_thumbprint

    if thumbprint:
        certs = crypto_pro.certs.find(thumbprint=thumbprint)
        if not certs:
            raise SignerError(f"сертификат с отпечатком {thumbprint} не найден")
        return certs[0]

    certs = crypto_pro.certs.all()
    if not certs:
        raise SignerError(
            "в хранилище нет ни одного сертификата — "
            "проверьте, что ключевой контейнер разложен в /var/opt/cprocsp/keys"
        )

    # Отпечаток не задан: предпочитаем действующий сертификат просроченному,
    # иначе подпись упадёт с 0x800B0101 (CERT_E_EXPIRED).
    for cert in certs:
        if cert.is_valid:
            return cert
    return certs[0]


def sign_detached(
    content: Union[bytes, str],
    *,
    thumbprint: Optional[str] = None,
    pin: Optional[str] = None,
) -> str:
    """
    Отделённая подпись CAdES-BES по хэшу ГОСТ Р 34.11-2012 (256).
    Возвращает base64-строку (PKCS#7).
    """
    cert = get_certificate(thumbprint)
    try:
        return cert.sign(
            content,
            pin=pin if pin is not None else settings.cert_pin,
            check_certificate=settings.check_certificate,
            formatted=settings.formatted_signature,
        )
    except Exception as exc:  # noqa: BLE001
        raise SignerError(f"не удалось создать подпись: {exc}") from exc


def verify_detached(content: Union[bytes, str], signature: str) -> bool:
    """Проверка отделённой подписи, созданной sign_detached."""
    return CryptoPro.verify(content, signature)


def gost_hash(content: Union[bytes, str]) -> str:
    """Хэш ГОСТ Р 34.11-2012 (256) в base64."""
    return CryptoPro.gost_hash(content)
