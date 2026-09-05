"""
HTTP-сервис электронной подписи на КриптоПро CSP + pycades.

Swagger UI: http://127.0.0.1:8011/docs
ReDoc:      http://127.0.0.1:8011/redoc

Запуск вне Docker (расширение pycades уже должно быть в PYTHONPATH):
    uvicorn main:app --host 0.0.0.0 --port 8011 --reload
"""

import base64
from typing import List, Optional

from fastapi import Body, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

import signer

app = FastAPI(
    title="pycades sign service",
    description="Отделённая подпись ГОСТ через КриптоПро CSP и расширение pycades",
    version="1.0.0",
)


# --------------------------------------------------------------------- модели


class SignRequest(BaseModel):
    data: str = Field(..., description="Подписываемые данные в base64")
    thumbprint: Optional[str] = Field(None, description="Отпечаток сертификата (SHA-1)")
    pin: Optional[str] = Field(None, description="Пин-код контейнера, если не задан в окружении")


class SignResponse(BaseModel):
    signature: str = Field(..., description="Отделённая подпись PKCS#7 в base64")
    thumbprint: str


class VerifyRequest(BaseModel):
    data: str = Field(..., description="Исходные данные в base64")
    signature: str = Field(..., description="Отделённая подпись в base64")


class CertificateInfo(BaseModel):
    thumbprint: str
    subject: str
    issuer: str
    serial_number: str
    valid_from: str
    valid_to: str
    has_private_key: bool
    is_valid: bool
    container: Optional[str] = None


# ------------------------------------------------------------- вспомогательное


def _decode(data: str) -> bytes:
    """base64 -> bytes, терпимо к переносам строк и пробелам."""
    cleaned = data.strip().replace("\n", "").replace("\r", "").replace(" ", "")
    try:
        return base64.b64decode(cleaned, validate=True)
    except (base64.binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"некорректная base64-строка: {exc}") from exc


def _handle(exc: Exception) -> HTTPException:
    if isinstance(exc, signer.SignerError):
        return HTTPException(status_code=422, detail=str(exc))
    return HTTPException(status_code=500, detail=f"внутренняя ошибка: {exc}")


# ------------------------------------------------------------------ служебное


@app.get("/health", summary="Проверка живости сервиса")
async def health():
    try:
        version = signer.module_version()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"pycades недоступен: {exc}") from exc
    return {"status": "ok", "pycades": version}


@app.get("/certificates", response_model=List[CertificateInfo], summary="Список сертификатов")
async def certificates():
    try:
        return signer.list_certificates()
    except Exception as exc:  # noqa: BLE001
        raise _handle(exc) from exc


# -------------------------------------------------------------------- подпись


@app.post("/sign", response_model=SignResponse, summary="Подписать данные (base64)")
async def sign(request: SignRequest = Body(...)):
    content = _decode(request.data)
    try:
        signature = signer.sign_detached(
            content, thumbprint=request.thumbprint, pin=request.pin
        )
        thumbprint = signer.get_certificate(request.thumbprint).thumbprint
    except Exception as exc:  # noqa: BLE001
        raise _handle(exc) from exc
    return SignResponse(signature=signature, thumbprint=thumbprint)


@app.post("/sign/file", response_model=SignResponse, summary="Подписать загруженный файл")
async def sign_file(
    file: UploadFile = File(..., description="Файл, который нужно подписать"),
    thumbprint: Optional[str] = Query(None),
    pin: Optional[str] = Query(None),
):
    content = await file.read()
    try:
        signature = signer.sign_detached(content, thumbprint=thumbprint, pin=pin)
        used = signer.get_certificate(thumbprint).thumbprint
    except Exception as exc:  # noqa: BLE001
        raise _handle(exc) from exc
    return SignResponse(signature=signature, thumbprint=used)


@app.post("/verify", summary="Проверить отделённую подпись")
async def verify(request: VerifyRequest = Body(...)):
    content = _decode(request.data)
    try:
        return {"valid": signer.verify_detached(content, request.signature)}
    except Exception as exc:  # noqa: BLE001
        raise _handle(exc) from exc


@app.post("/hash", summary="Хэш ГОСТ Р 34.11-2012 (256) в base64")
async def gost_hash(request: SignRequest = Body(...)):
    content = _decode(request.data)
    try:
        return {"hash": signer.gost_hash(content)}
    except Exception as exc:  # noqa: BLE001
        raise _handle(exc) from exc


# ------------------------------------------------------- совместимость с 1С


@app.post(
    "/sign-xml/",
    summary="Устаревший метод: подписать XML и вернуть файл .sgn",
    description=(
        "Оставлен для совместимости с уже написанными вызовами из 1С. "
        "Принимает base64 в поле data, возвращает подпись как вложение document.sgn. "
        "В новом коде используйте POST /sign."
    ),
    deprecated=True,
)
async def sign_xml(request: SignRequest = Body(...)):
    content = _decode(request.data)
    try:
        signature = signer.sign_detached(
            content, thumbprint=request.thumbprint, pin=request.pin
        )
    except Exception as exc:  # noqa: BLE001
        raise _handle(exc) from exc

    return Response(
        content=signature,
        media_type="application/octet-stream",
        headers={"Content-Disposition": "attachment; filename=document.sgn"},
    )


# ----------------------------------------------------- демо-методы для 1С


@app.get("/demo/id", summary="Демо: вернуть UUID")
async def demo_id():
    import uuid

    return {"id": str(uuid.uuid4())}


@app.get("/demo/text", summary="Демо: отдать текстовый файл")
async def demo_text():
    return FileResponse("/samples/example.txt", media_type="text/plain")


@app.get("/demo/binary", summary="Демо: отдать двоичный файл")
async def demo_binary():
    return FileResponse("/samples/test_image.jpg", media_type="application/octet-stream")
