# Шпаргалка по командам КриптоПро CSP

Все утилиты лежат в `/opt/cprocsp/bin/amd64` и `/opt/cprocsp/sbin/amd64`.
В образе эти каталоги добавлены в `PATH`, поэтому внутри контейнера можно
писать просто `certmgr`, `cryptcp`, `csptest`.

Зайти в контейнер:

```bash
docker compose exec pycades bash
```

## Лицензия

```bash
cpconfig -license -view              # посмотреть текущую
cpconfig -license -set <СЕРИЙНЫЙ_НОМЕР>
```

Без лицензии CSP работает 90 дней в демо-режиме. Серийный номер удобнее
задавать через `CSP_LICENSE` в `.env` — его подставит entrypoint при старте.

## Ключевые контейнеры

Контейнеры пользователя лежат в `/var/opt/cprocsp/keys/<имя_пользователя>/`,
контейнеры компьютера — в `/var/opt/cprocsp/keys/root/`.

```bash
# перечислить все видимые контейнеры
csptest -keyset -enum_cont -verifycontext -fqcn

# то же для контейнеров компьютера
csptest -keyset -enum_cont -verifycontext -fqcn -machinekeys

# проверить конкретный контейнер
csptest -keyset -check -cont '\\.\HDIMAGE\<имя_контейнера>'
csptest -keyset -check -cont '\\.\HDIMAGE\<имя_контейнера>' -machinekeyset

# скопировать контейнер вручную (обычно это делает entrypoint.sh)
cp -r /opt/keys/test1.000 /var/opt/cprocsp/keys/root/
chmod 700 /var/opt/cprocsp/keys/root/test1.000
```

Имя контейнера в кавычках обязательно, если в нём есть пробелы.

## Сертификаты

```bash
certmgr -list                                  # сертификаты в хранилище uMy
certmgr -list -store mRoot                     # корневые
certmgr -inst -store mRoot -file EasyCert.cer  # установить корневой
certmgr -inst -cont '\\.\HDIMAGE\<контейнер>'  # привязать сертификат к контейнеру
certmgr -delete -thumbprint <отпечаток>
certmgr -export -thumbprint <отпечаток> -dest out.cer
certmgr -enumstores                            # список хранилищ
```

Обёртка `pycades` открывает хранилище как `CADESCOM_CONTAINER_STORE`,
то есть читает сертификаты прямо из ключевых контейнеров. Отдельно ставить
их в `uMy` через `certmgr -inst` обычно не требуется — достаточно, чтобы
контейнер был разложен в `/var/opt/cprocsp/keys/`.

## Подпись из командной строки

```bash
# отделённая подпись файла
cryptcp -sign -uMy -thumbprint <отпечаток> -pin '<пин>' -der input.xml output.sig

# подпись всех файлов в 'source_file.sgn'
cryptcp -signf -thumbprint <отпечаток> input.xml

# проверка
cryptcp -vsignf input.xml.sgn

# создать сертификат в тестовом УЦ КриптоПро
cryptcp -createcert -dn "CN=test" -provtype 80 \
        -cont '\\.\HDIMAGE\test' -ca https://cryptopro.ru/certsrv

# установить сертификат в контейнер
cryptcp -instcert -cont '\\.\HDIMAGE\test' mycert.cer
```

Полный список команд: `cryptcp -help`, `certmgr -help`, `csptest -help`.

## Цепочки доверия и OpenSSL

```bash
# der -> pem
openssl x509 -inform der -in newcert.cer -out newcert.crt

# вытащить все сертификаты из p7b
openssl pkcs7 -inform DER -in certnew.p7b -print_certs -out certnew.pem

# добавить в системное хранилище
cp certnew.pem /usr/local/share/ca-certificates/certnew.crt
update-ca-certificates

openssl verify newcert.crt
```

Файлы `.crt` из каталога `certs/` проекта entrypoint раскладывает в оба
хранилища автоматически: в `mRoot` для КриптоПро и в системное для OpenSSL.

## Диагностика

```bash
csptest -enum                        # параметры провайдеров
csptest -keyset -verifycontext       # доступность контекста
python3 -c "import pycades; print(pycades.ModuleVersion())"
```

Если `import pycades` падает с `ImportError`, проверьте `PYTHONPATH`
(должен указывать на `/opt/pycades`) и `LD_LIBRARY_PATH`
(`/opt/cprocsp/lib/amd64`).
