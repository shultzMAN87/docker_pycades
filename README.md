# 11_pycades — КриптоПро CSP + pycades в Docker

Docker-окружение, которое собирает расширение [pycades](https://github.com/CryptoPro/pycades)
(`pycades.so`) поверх КриптоПро CSP и поднимает поверх него HTTP-сервис
электронной подписи ГОСТ на FastAPI.

Зачем: получить отделённую подпись ГОСТ Р 34.10-2012 из любой системы, которая
умеет ходить по HTTP, — например из 1С:Предприятие, где нативной работы
с КриптоПро под Linux нет.

## Что внутри

* сборка `pycades.so` из исходников с фиксацией версии по тегу;
* установка КриптоПро CSP из вашего дистрибутива, без привязки к номеру версии;
* автоматическая раскладка ключевых контейнеров и корневых сертификатов при старте;
* FastAPI-сервис: подпись, проверка, хэш, список сертификатов, Swagger UI;
* смоук-тест одной командой;
* тестовый сертификат для проверки подписи ставится одной переменной.

## Проверено на

| Компонент | Версия |
|---|---|
| КриптоПро CSP | 5.0.13800 (KC1, Type 80) |
| pycades | 0.1.70300 |
| Базовый образ | ubuntu:24.04, Python 3.12 |
| Хост | Docker Desktop на Windows |

Проверялся полный цикл: сборка `pycades.so`, установка CSP, импорт `.pfx`,
`POST /sign` и `POST /verify` — подпись создаётся и проходит проверку.

## Требования

* Docker и Docker Compose v2 (`docker compose`, не `docker-compose`);
* архитектура x86-64 (дистрибутив CSP — `linux-amd64_deb`);
* дистрибутив КриптоПро CSP — скачивается отдельно, см. ниже;
* ключевой контейнер с закрытым ключом (для боевого использования).

## Быстрый старт

**1. Положите дистрибутив КриптоПро CSP**

Скачайте с https://cryptopro.ru/products/csp/downloads
(«Скачать для Windows» ▾ → **Linux DEB x64**, нужна бесплатная регистрация)
и положите в проект как `csp/linux-amd64_deb.tgz`.

Файл лицензионный, поэтому в репозиторий он не входит и добавлен в `.gitignore`.
Подробнее — `csp/README.md`.

**2. Запустите**

```bash
docker compose up -d --build
```

Всё. Больше ничего настраивать не нужно: без файла `.env` подставляются
значения по умолчанию, и проект стартует на демонстрационном контейнере
`keys/test1.000`.

Первая сборка идёт долго — компилируется C++-расширение. Дальше `--build`
нужен, только если вы меняли `Dockerfile` или `requirements.txt`: код
приложения примонтирован томом и подхватывается без пересборки.

Дождаться готовности сервиса (в образе есть healthcheck):

```bash
docker compose up -d --build --wait
```

**3. Проверьте**

```bash
curl http://127.0.0.1:8011/health
curl http://127.0.0.1:8011/certificates
docker compose exec pycades python selftest.py
```

`selftest.py` выводит версию pycades, список сертификатов, хэш, полученную
подпись и результат её проверки.

Swagger UI: http://127.0.0.1:8011/docs

**4. Только если нужно поменять настройки**

```bash
cp .env.example .env
```

Файл `.env` подхватывается автоматически — он нужен, чтобы задать свой
сертификат, пин-код, порт или лицензию. Для запуска как такового он не нужен.

**Makefile** в проекте есть, но это просто сокращения (`make up`, `make logs`,
`make selftest`). Всё то же самое делается штатными командами `docker compose`.

## Тестовый сертификат

Демонстрационный контейнер `keys/test1.000` **просрочен 03.01.2026**. Подписать
им уже нельзя: КриптоПро вернёт `0x800B0101` (`CERT_E_EXPIRED`) даже при
`CHECK_CERTIFICATE=false` — срок действия проверяется всегда, отключается только
проверка цепочки и отзыва.

Ниже три способа получить рабочий сертификат для тестов, от простого к сложному.

### Вариант 1. Готовые фикстуры pycades (рекомендуется)

В исходниках pycades, которые остаются внутри образа, лежит тестовая связка:
корневой `pycades-root` и выпущенный им `pycades-test`. Сертификат действует
**до 2050 года**, пароль пустой. Ничего скачивать и выпускать не нужно.

Включите в `.env`:

```
SETUP_TEST_CERT=true
```

и перезапустите:

```bash
docker compose up -d
docker compose exec pycades python selftest.py
```

`entrypoint.sh` при старте поставит корневой в `uRoot`, список отзыва в `uCA`
и импортирует `pycades-test.pfx` в личное хранилище. Повторные запуски
пропускают шаг, если сертификат уже на месте.

Если отпечаток в `CERT_THUMBPRINT` не задан, сервис сам выберет действующий
сертификат, а не просроченный, — так что `keys/test1.000` можно и не удалять.

### Вариант 2. Тестовый УЦ КриптоПро

Выдаёт сертификат на 3 месяца. Нужен доступ из контейнера к `cryptopro.ru`.

```bash
docker compose exec pycades bash

# создать контейнер и запросить сертификат
cryptcp -createcert -dn "CN=test-sign" -provtype 80 \
        -cont '\\.\HDIMAGE\testsign' \
        -ca https://www.cryptopro.ru/certsrv

# проверить
certmgr -list
```

Корневой сертификат тестового УЦ КриптоПро уже лежит в `certs/certnew.cer`
и ставится в `mRoot` автоматически.

Чтобы контейнер пережил пересоздание образа, скопируйте его в проект:

```bash
docker compose exec pycades bash -c 'cp -r /var/opt/cprocsp/keys/root/*.000 /tmp/'
docker compose cp pycades:/tmp/testsign.000 ./keys/
```

### Вариант 3. Свой PFX

Конвертировать `.pfx` в каталог вида `test1.000` вручную не нужно — положите
файл в `keys/` как есть:

```bash
cp mycert.pfx keys/
docker compose restart
docker compose logs pycades | grep PFX
```

`entrypoint.sh` при старте импортирует его командой `certmgr -install -pfx`,
КриптоПро сам создаст ключевой контейнер. Пароль от файла задаётся в `.env`
через `PFX_PASSWORD`, пин создаваемого контейнера — через `CERT_PIN`
(можно оставить пустым). Файлы `.pfx` и `.p12` закрыты в `.gitignore`.

Импорт идемпотентный: повторные запуски пропускают уже импортированные файлы,
дубликаты контейнеров не плодятся.

Работают оба формата одновременно — можно держать в `keys/` и готовые каталоги
`*.000`, и файлы `*.pfx`.

**Если всё-таки нужен каталог `.000`** — например, чтобы не зависеть от пароля
или переносить контейнер между машинами, — импортируйте PFX один раз
и заберите готовый контейнер из образа:

```bash
docker compose exec pycades ls /var/opt/cprocsp/keys/root/
docker compose cp pycades:/var/opt/cprocsp/keys/root/<имя>.000 ./keys/
rm keys/mycert.pfx
```

После этого контейнер будет раскладываться из `keys/` обычным способом,
а `PFX_PASSWORD` больше не понадобится.

### После получения сертификата

```bash
curl -s http://127.0.0.1:8011/certificates | python3 -m json.tool
```

Возьмите нужный `thumbprint`, пропишите его в `CERT_THUMBPRINT` и перезапустите
сервис. Для боевого сертификата имеет смысл включить `CHECK_CERTIFICATE=true`.

## Работа со своим сертификатом

1. Положите каталог контейнера в `keys/`:

   ```bash
   cp -r /путь/до/mycontainer.000 keys/
   ```

2. Узнайте отпечаток сертификата:

   ```bash
   docker compose restart
   curl -s http://127.0.0.1:8011/certificates | python3 -m json.tool
   ```

3. Пропишите в `.env`:

   ```
   CERT_THUMBPRINT=8ead04af927b80ec4f43f5dc11796fa682565b8a
   CERT_PIN=пин_от_контейнера
   CHECK_CERTIFICATE=true
   ```

4. Перезапустите: `docker compose restart`

Если корневой сертификат вашего УЦ ещё не в списке — положите его в `certs/`
(см. `certs/README.md`).

**Реальные контейнеры и пин-коды в git не коммитятся.** `.env` и `keys/*.000/`
(кроме демонстрационного) закрыты в `.gitignore`.

## API

| Метод | Путь | Назначение |
|---|---|---|
| GET | `/health` | живость сервиса и версия pycades |
| GET | `/certificates` | сертификаты с закрытым ключом |
| POST | `/sign` | подписать данные из base64 → подпись в JSON |
| POST | `/sign/file` | подписать загруженный файл → подпись в JSON |
| POST | `/verify` | проверить отделённую подпись |
| POST | `/hash` | хэш ГОСТ Р 34.11-2012 (256) в base64 |
| POST | `/sign-xml/` | устаревший: подпись возвращается файлом `document.sgn` |
| GET | `/demo/id`, `/demo/text`, `/demo/binary` | демо-ручки для проверки обмена с 1С |

Подпись — отделённая (detached) CAdES-BES по хэшу ГОСТ Р 34.11-2012 (256),
результат в base64 (PKCS#7).

### Пример

```bash
DATA=$(echo -n 'подписываемые данные' | base64 -w0)

SIG=$(curl -s -X POST http://127.0.0.1:8011/sign \
  -H 'Content-Type: application/json' \
  -d "{\"data\":\"$DATA\"}" | python3 -c 'import sys,json; print(json.load(sys.stdin)["signature"])')

curl -s -X POST http://127.0.0.1:8011/verify \
  -H 'Content-Type: application/json' \
  -d "{\"data\":\"$DATA\",\"signature\":\"$SIG\"}"
```

### Вызов из 1С

```bsl
ДвоичныеДанные = ПолучитьДвоичныеДанныеИзСтроки(ТекстXML);
Base64 = Base64Строка(ДвоичныеДанные);

Соединение = Новый HTTPСоединение("127.0.0.1", 8011);

Запрос = Новый HTTPЗапрос("/sign");
Запрос.Заголовки.Вставить("Content-Type", "application/json");

Тело = Новый Структура("data", Base64);
ЗаписьJSON = Новый ЗаписьJSON;
ЗаписьJSON.УстановитьСтроку();
ЗаписатьJSON(ЗаписьJSON, Тело);
Запрос.УстановитьТелоИзСтроки(ЗаписьJSON.Закрыть());

Ответ = Соединение.ОтправитьДляОбработки(Запрос);
```

`POST /sign-xml/` оставлен как алиас с прежним поведением (возвращает подпись
вложением `document.sgn`), чтобы уже написанные вызовы не пришлось переписывать.
В новом коде используйте `/sign`.

## Переменные окружения

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `APP_PORT` | `8011` | порт на хосте |
| `PYCADES_REF` | `v0.1.70300` | тег pycades для сборки |
| `UBUNTU_VERSION` | `24.04` | базовый образ |
| `CERT_THUMBPRINT` | пусто | отпечаток сертификата по умолчанию; пусто — первый доступный |
| `CERT_PIN` | пусто | пин-код контейнера |
| `CHECK_CERTIFICATE` | `false` | проверять цепочку и отзыв перед подписью |
| `SETUP_TEST_CERT` | `false` | ставить при старте тестовый `pycades-test` (до 2050) |
| `PFX_PASSWORD` | пусто | пароль от файла `.pfx` в `keys/` |
| `CSP_LICENSE` | пусто | серийный номер КриптоПро CSP |

Без `CSP_LICENSE` КриптоПро CSP работает 90 дней в демо-режиме.

## Структура проекта

```
11_pycades/
├── compose.yml                    описание сервиса
├── Makefile                       частые команды
├── .env.example                   шаблон настроек
├── csp/                           сюда кладётся дистрибутив КриптоПро CSP
├── docker/
│   └── Dockerfile                 сборка: Ubuntu 24.04 / Python 3.12
├── scripts/
│   ├── install-csp.sh             установка CSP на этапе сборки
│   └── entrypoint.sh              раскладка ключей и сертификатов при старте
├── app/
│   ├── main.py                    HTTP-слой (FastAPI)
│   ├── signer.py                  логика подписи
│   ├── config.py                  настройки из окружения
│   ├── selftest.py                смоук-тест
│   ├── requirements.txt
│   └── vendor/cryptopro/          обёртка над pycades (volstr/cryptopro, MIT)
├── certs/                         сертификаты УЦ → mRoot при старте
├── keys/                          ключевые контейнеры → /var/opt/cprocsp/keys
├── samples/                       файлы для демо-ручек
└── docs/
    ├── cryptopro-cheatsheet.md    команды cryptcp / certmgr / csptest
    └── notes.md                   что откуда собрано и что исправлено
```

## Команды

Всё делается штатным `docker compose`; `make` — необязательные сокращения.

| Задача | docker compose | make |
|---|---|---|
| собрать и поднять | `docker compose up -d --build` | `make build && make up` |
| поднять (образ уже собран) | `docker compose up -d` | `make up` |
| дождаться готовности | `docker compose up -d --wait` | — |
| остановить | `docker compose down` | `make down` |
| логи | `docker compose logs -f` | `make logs` |
| bash внутри | `docker compose exec pycades bash` | `make shell` |
| смоук-тест | `docker compose exec pycades python selftest.py` | `make selftest` |
| список сертификатов | `docker compose exec pycades certmgr -list` | `make certs` |
| удалить всё | `docker compose down --rmi local` | `make clean` |

## Windows и PowerShell

В PowerShell нет `grep`, а `curl` — это псевдоним для `Invoke-WebRequest`
с другим поведением. Эквиваленты команд из этого README:

| bash | PowerShell |
|---|---|
| `curl http://127.0.0.1:8011/health` | `curl.exe http://127.0.0.1:8011/health` |
| `... \| grep -i pfx` | `... \| Select-String pfx` |
| `... \| python3 -m json.tool` | `... \| ConvertFrom-Json \| ConvertTo-Json` |

`curl.exe` с расширением вызывает настоящий curl, который есть в Windows 10
и 11 из коробки, и не выдаёт предупреждение про разбор веб-страницы.

Посмотреть, что сделал entrypoint при старте:

```powershell
docker compose logs pycades | Select-String "entrypoint"
```

## Если что-то не работает

**`import pycades` падает с ImportError**

Проверьте внутри контейнера:

```bash
echo $PYTHONPATH          # ожидается /opt/pycades
ls -l /opt/pycades/pycades.so
echo $LD_LIBRARY_PATH     # ожидается /opt/cprocsp/lib/amd64
```

**`/certificates` возвращает пустой список**

Контейнер не разложен или не читается:

```bash
docker compose exec pycades csptest -keyset -enum_cont -verifycontext -fqcn
docker compose exec pycades ls -la /var/opt/cprocsp/keys/root/
docker compose logs pycades | head -40
```

Права на каталог контейнера должны быть 700, на файлы внутри — 600;
`entrypoint.sh` выставляет их сам.

**Подпись падает с `0x800B0101`**

Это `CERT_E_EXPIRED` — сертификат просрочен. Демо-контейнер `keys/test1.000`
истёк 03.01.2026, и `CHECK_CERTIFICATE=false` тут не помогает: срок действия
КриптоПро проверяет всегда. Возьмите рабочий сертификат — см. раздел
«Тестовый сертификат», самый быстрый путь `SETUP_TEST_CERT=true`.

**Подпись падает на проверке цепочки или отзыва**

Поставьте `CHECK_CERTIFICATE=false` в `.env` либо положите недостающий корневой
сертификат УЦ в `certs/` и перезапустите сервис.

**PFX не импортируется, сертификатов по-прежнему не видно**

Сначала проверьте, что файл лежит в `keys/`, а не в `certs/`. В `certs/`
обрабатываются только `.cer` и `.crt` — это хранилище корневых сертификатов УЦ,
ключи туда не попадают. Entrypoint пишет об этом в лог при старте.

Если файл на месте, но импорт не прошёл, entrypoint выведет в лог настоящую
ошибку `certmgr` — смотрите её:

```bash
docker compose logs pycades
```

Что проверить дальше:

* **пароль.** `PFX_PASSWORD` в `.env` — это пароль от самого файла `.pfx`.
  Если пароля нет, переменную оставьте пустой, `-pin` тогда не передаётся вовсе.
* **имя файла.** Пробелы, скобки и кириллица в имени `certmgr` переваривает
  плохо. Entrypoint копирует файл во временный путь с безопасным именем, но
  если проблема осталась — переименуйте, например в `cert.pfx`.
* **алгоритм ключа.** КриптоПро импортирует только ГОСТовые контейнеры.
  PFX с RSA-ключом отвалится с ошибкой про неподдерживаемый алгоритм.

Импортировать вручную и увидеть вывод целиком:

```bash
docker compose exec pycades bash
cp /opt/keys/*.pfx /tmp/c.pfx
certmgr -install -pfx -file /tmp/c.pfx -pin 'ваш_пароль' -newpin ''
certmgr -list
```

**Правки в `scripts/entrypoint.sh` не применились**

Если в выводе сборки строка `COPY scripts/entrypoint.sh` помечена `CACHED`,
значит файл на диске не изменился — например, архив распаковался во вложенный
каталог `11_pycades/11_pycades/`, или распаковщик не стал перезаписывать файлы.
Признак того же: в конце `docker compose up` контейнер помечен `Running`,
а не `Recreated`.

Проверить, какая версия попала в образ:

```bash
docker compose exec pycades grep -c MARKER_DIR /usr/local/bin/entrypoint.sh
```

Ноль или ошибка — в образе старая версия.

**Сборка падает на `install-csp.sh`**

Скорее всего `csp/linux-amd64_deb.tgz` пустой или это не тот архив.
Скрипт проверяет наличие `install.sh` внутри и пишет об этом явно.

**Сборка падает на клонировании pycades**

Проверьте `PYCADES_REF` в `.env`. Не ставьте `main`: upstream в марте 2026
сменил структуру репозитория, и рецепт сборки может измениться снова.

## Замечания по безопасности

* Дистрибутив КриптоПро CSP лицензионный — в репозиторий не выкладывается.
* `.env` с пин-кодом закрыт в `.gitignore`. Пин-коды в исходниках не хранятся.
* `keys/test1.000` — просроченный контейнер тестового УЦ, включён намеренно
  как демонстрационный. Реальные контейнеры игнорируются git-ом.
* Сервис не имеет аутентификации: любой, кто дотянется до порта 8011, сможет
  подписывать вашим ключом. Не публикуйте его наружу — держите в закрытом
  контуре или закройте reverse-proxy с авторизацией.
* Контейнер работает от root: так требует раскладка ключей в
  `/var/opt/cprocsp/keys/root/`.

## Лицензии и источники

* [CryptoPro/pycades](https://github.com/CryptoPro/pycades) — расширение,
  собирается из исходников, лицензия в репозитории upstream.
* [volstr/cryptopro](https://github.com/volstr/cryptopro) — обёртка в
  `app/vendor/cryptopro/`, MIT, текст лицензии приложен.
* КриптоПро CSP — проприетарный продукт ООО «КРИПТО-ПРО», распространяется
  по собственной лицензии и в этот репозиторий не входит.

Документация: https://docs.cryptopro.ru/cades/pycades

История сборки и разбор того, что было исправлено, — в `docs/notes.md`.
