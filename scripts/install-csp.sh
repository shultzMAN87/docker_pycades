#!/bin/bash
# Установка КриптоПро CSP из архива дистрибутива (linux-amd64_deb.tgz).
# Выполняется на этапе сборки образа.
#
# Использование: install-csp.sh /путь/до/linux-amd64_deb.tgz

set -euo pipefail

TGZ="${1:?не указан путь к архиву дистрибутива КриптоПро CSP}"
WORK=/tmp/csp-unpack

if [ ! -s "$TGZ" ]; then
    echo "ОШИБКА: файл '$TGZ' пустой или отсутствует." >&2
    echo "Положите настоящий дистрибутив КриптоПро CSP в csp/linux-amd64_deb.tgz" >&2
    echo "https://cryptopro.ru/products/csp/downloads -> Linux DEB x64" >&2
    exit 1
fi

rm -rf "$WORK"
mkdir -p "$WORK"
tar xf "$TGZ" -C "$WORK"

# Внутри архива обычно есть каталог linux-amd64_deb, но имя может отличаться,
# поэтому ищем каталог, в котором лежит install.sh.
CSP_DIR="$(dirname "$(find "$WORK" -maxdepth 3 -name install.sh -type f | head -n 1)")"
if [ -z "$CSP_DIR" ] || [ ! -f "$CSP_DIR/install.sh" ]; then
    echo "ОШИБКА: в архиве не найден install.sh — это точно дистрибутив КриптоПро CSP?" >&2
    exit 1
fi

cd "$CSP_DIR"
chmod +x install.sh

echo ">>> Базовая установка КриптоПро CSP"
./install.sh

echo ">>> Доустановка пакетов, нужных для сборки и работы pycades"
apt-get update

# Маски пакетов. Версии не фиксируем — они зависят от дистрибутива,
# который вы скачали с сайта КриптоПро.
#   lsb-cprocsp-devel     — заголовочные файлы, без них не собрать pycades
#   cprocsp-pki-cades-64  — библиотека libcppcades, с которой линкуется pycades
#   cprocsp-pki-phpcades  — не нужен для pycades, ставится только если есть
#   cprocsp-legacy-*      — поддержка legacy-алгоритмов, есть не во всех сборках
for mask in \
    'lsb-cprocsp-devel_*.deb' \
    'cprocsp-pki-cades-64_*.deb' \
    'cprocsp-pki-cades_*.deb' \
    'cprocsp-legacy-*.deb' \
; do
    # shellcheck disable=SC2086
    files=$(ls $mask 2>/dev/null || true)
    if [ -n "$files" ]; then
        echo "    ставлю: $files"
        # shellcheck disable=SC2086
        apt-get install -y --no-install-recommends $(printf './%s ' $files)
    else
        echo "    пропускаю (нет в дистрибутиве): $mask"
    fi
done

rm -rf /var/lib/apt/lists/* "$WORK"

echo ">>> Установленные пакеты КриптоПро:"
dpkg -l | grep -E 'cprocsp|lsb-cprocsp' || true
