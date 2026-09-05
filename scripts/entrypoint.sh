#!/bin/bash
# Подготовка окружения КриптоПро при каждом старте контейнера:
#   1) лицензия (если задана);
#   2) ключевые контейнеры  /opt/keys/*.000  ->  /var/opt/cprocsp/keys/<user>/;
#   3) корневые сертификаты /opt/certs/*     ->  хранилище mRoot + системный ca-certificates.
#
# Каталоги /opt/keys и /opt/certs монтируются из проекта (см. compose.yml).

set -euo pipefail

CPROCSP_BIN=/opt/cprocsp/bin/amd64
CPROCSP_SBIN=/opt/cprocsp/sbin/amd64
KEYS_SRC="${KEYS_SRC:-/opt/keys}"
CERTS_SRC="${CERTS_SRC:-/opt/certs}"
USER_NAME="$(id -un)"
KEYS_DST="/var/opt/cprocsp/keys/${USER_NAME}"

log() { printf '[entrypoint] %s\n' "$*"; }

# ------------------------------------------------------------------- лицензия
if [ -n "${CSP_LICENSE:-}" ]; then
    log "устанавливаю серийный номер КриптоПро CSP"
    "${CPROCSP_SBIN}/cpconfig" -license -set "${CSP_LICENSE}" || \
        log "ПРЕДУПРЕЖДЕНИЕ: не удалось установить лицензию"
fi
log "лицензия: $("${CPROCSP_SBIN}/cpconfig" -license -view 2>/dev/null | tr '\n' ' ' || echo 'не определена')"

# --------------------------------------------------------- ключевые контейнеры
if [ -d "${KEYS_SRC}" ]; then
    mkdir -p "${KEYS_DST}"
    shopt -s nullglob
    for container in "${KEYS_SRC}"/*.000; do
        name="$(basename "${container}")"
        # Копируем, а не монтируем: КриптоПро пишет в контейнер и требует прав 0700
        rm -rf "${KEYS_DST:?}/${name}"
        cp -r "${container}" "${KEYS_DST}/${name}"
        chmod 700 "${KEYS_DST}/${name}"
        chmod 600 "${KEYS_DST}/${name}"/*
        log "контейнер установлен: ${name}"
    done
    shopt -u nullglob
fi

# ------------------------------------------ тестовый сертификат pycades
# Фикстуры лежат в исходниках pycades внутри образа: сертификат pycades-test,
# выпущенный тестовым УЦ pycades-root, действует до 2050 года, пароль пустой.
# Включается переменной SETUP_TEST_CERT=true.
PYCADES_FIXTURES="${PYCADES_FIXTURES:-/usr/src/pycades/tests/fixtures}"
if [ "${SETUP_TEST_CERT:-false}" = "true" ]; then
    if [ -f "${PYCADES_FIXTURES}/pycades-test.pfx" ]; then
        if "${CPROCSP_BIN}/certmgr" -list -store uMy 2>/dev/null | grep -q 'pycades-test'; then
            log "тестовый сертификат pycades-test уже установлен"
        else
            echo 'o' | "${CPROCSP_BIN}/certmgr" -install -file "${PYCADES_FIXTURES}/pycades-root.cer" \
                -store uRoot >/dev/null 2>&1 || true
            echo 'o' | "${CPROCSP_BIN}/certmgr" -install -crl -file "${PYCADES_FIXTURES}/pycades-root.crl" \
                -store uCA >/dev/null 2>&1 || true
            if "${CPROCSP_BIN}/certmgr" -install -pfx -file "${PYCADES_FIXTURES}/pycades-test.pfx" \
                -newpin "" >/dev/null 2>&1; then
                log "установлен тестовый сертификат pycades-test (действует до 2050, пин пустой)"
            else
                log "ПРЕДУПРЕЖДЕНИЕ: не удалось установить pycades-test.pfx"
            fi
        fi
    else
        log "ПРЕДУПРЕЖДЕНИЕ: фикстуры pycades не найдены в ${PYCADES_FIXTURES}"
    fi
fi

# ---------------------------------------------------- контейнеры из PFX
# Любой файл keys/*.pfx или keys/*.p12 импортируется в хранилище при старте.
# Пароль самого PFX — PFX_PASSWORD, пин создаваемого контейнера — CERT_PIN.
#
# certmgr при каждом импорте создаёт новый контейнер со случайным именем,
# поэтому повторный запуск плодил бы дубликаты. Отмечаем уже импортированные
# файлы маркером по хэшу: маркеры лежат в файловой системе контейнера и
# пропадают вместе с ней, то есть ровно тогда, когда пропадают и сами ключи.
MARKER_DIR=/var/lib/pycades/imported
mkdir -p "${MARKER_DIR}"

if [ -d "${KEYS_SRC}" ]; then
    shopt -s nullglob
    for pfx in "${KEYS_SRC}"/*.pfx "${KEYS_SRC}"/*.p12; do
        name="$(basename "${pfx}")"
        marker="${MARKER_DIR}/${name}.$(md5sum "${pfx}" | cut -c1-12)"

        if [ -f "${marker}" ]; then
            log "PFX уже импортирован, пропускаю: ${name}"
            continue
        fi

        # certmgr спотыкается о пробелы, скобки и кириллицу в пути,
        # поэтому импортируем через временную копию с безопасным именем
        tmp_pfx="/tmp/pfx-import$(printf '%s' "${pfx}" | md5sum | cut -c1-8).pfx"
        cp "${pfx}" "${tmp_pfx}"

        args=(-install -pfx -file "${tmp_pfx}")
        # Пустые -pin/-newpin некоторые сборки certmgr разбирают как ошибку,
        # поэтому подставляем их только когда значение реально задано
        if [ -n "${PFX_PASSWORD:-}" ]; then
            args+=(-pin "${PFX_PASSWORD}")
        fi
        args+=(-newpin "${CERT_PIN:-}")

        if output="$("${CPROCSP_BIN}/certmgr" "${args[@]}" </dev/null 2>&1)"; then
            touch "${marker}"
            log "импортирован PFX: ${name}"
        else
            log "ПРЕДУПРЕЖДЕНИЕ: не удалось импортировать ${name}"
            printf '%s\n' "${output}" | sed 's/^/           /'
        fi
        rm -f "${tmp_pfx}"
    done
    shopt -u nullglob
fi

# ------------------------------------------------------ сертификаты и цепочки
if [ -d "${CERTS_SRC}" ]; then
    shopt -s nullglob
    for cert in "${CERTS_SRC}"/*.cer "${CERTS_SRC}"/*.crt; do
        "${CPROCSP_BIN}/certmgr" -inst -store mRoot -file "${cert}" >/dev/null 2>&1 \
            && log "в mRoot добавлен: $(basename "${cert}")" \
            || log "пропущен (уже есть или не корневой): $(basename "${cert}")"
    done
    # Те же сертификаты — в системное хранилище, чтобы работали проверки OpenSSL
    for cert in "${CERTS_SRC}"/*.crt; do
        cp -f "${cert}" /usr/local/share/ca-certificates/ 2>/dev/null || true
    done
    # Частая ошибка: .pfx кладут в certs/ вместо keys/
    for stray in "${CERTS_SRC}"/*.pfx "${CERTS_SRC}"/*.p12; do
        log "ВНИМАНИЕ: $(basename "${stray}") лежит в certs/, а импортируются только"
        log "          файлы из keys/ — перенесите его туда и перезапустите сервис"
    done
    shopt -u nullglob
    update-ca-certificates >/dev/null 2>&1 || true
fi

# ------------------------------------------------------------------ диагностика
log "контейнеры, видимые КриптоПро:"
"${CPROCSP_BIN}/csptest" -keyset -enum_cont -verifycontext -fqcn 2>/dev/null \
    | sed 's/^/           /' || log "           (csptest не отработал)"

exec "$@"
