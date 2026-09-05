#!/usr/bin/env python3
"""
Смоук-тест. Запускать внутри контейнера:

    docker compose exec pycades python selftest.py

Проверяет: импорт pycades, доступность контейнеров, подпись и её проверку.
"""

import sys

import signer


def main() -> int:
    print("pycades:", signer.module_version())

    certs = signer.list_certificates()
    if not certs:
        print("ОШИБКА: сертификаты не найдены.", file=sys.stderr)
        print("Проверьте, что контейнер разложен в /var/opt/cprocsp/keys/<user>/", file=sys.stderr)
        return 1

    print(f"\nнайдено сертификатов: {len(certs)}")
    for cert in certs:
        flag = "действителен" if cert["is_valid"] else "ПРОСРОЧЕН/НЕВАЛИДЕН"
        print(f"  {cert['thumbprint']}  {cert['subject']}  [{flag}]")
        print(f"      издатель:  {cert['issuer']}")
        print(f"      срок:      {cert['valid_from']} .. {cert['valid_to']}")
        print(f"      контейнер: {cert['container']}")

    data = "проверка подписи pycades"
    print(f"\nхэш ГОСТ 34.11-2012: {signer.gost_hash(data)}")

    try:
        signature = signer.sign_detached(data)
    except signer.SignerError as exc:
        print(f"\nОШИБКА подписи: {exc}", file=sys.stderr)
        if "800B0101" in str(exc):
            print(
                "0x800B0101 (CERT_E_EXPIRED) — сертификат просрочен. "
                "Срок действия КриптоПро проверяет всегда, CHECK_CERTIFICATE=false "
                "здесь не помогает.\n"
                "Нужен действующий сертификат: поставьте SETUP_TEST_CERT=true в .env "
                "или положите свой .pfx в keys/ — см. раздел «Тестовый сертификат» "
                "в README.",
                file=sys.stderr,
            )
        else:
            print(
                "Частые причины: не задан CERT_PIN, либо не выстраивается цепочка "
                "доверия при CHECK_CERTIFICATE=true.",
                file=sys.stderr,
            )
        return 1

    print(f"\nподпись получена, длина {len(signature)} символов")
    print("проверка подписи:", "OK" if signer.verify_detached(data, signature) else "НЕ ПРОЙДЕНА")
    return 0


if __name__ == "__main__":
    sys.exit(main())
