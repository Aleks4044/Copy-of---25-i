"""Тенок, дефанзивен клиент за sports.bzzoiro.com API (v2).

Клучот се чита од променливата на околината BZZOIRO_API_KEY, а само ако таа
не е поставена се користи наследната BIZZOIRO променлива исклучиво за
автентикација. Ниту една од вредностите НИКОГАШ не се логира ниту
прикажува во интерфејсот.
"""

import logging
import os

import requests

BASE_URL = "https://sports.bzzoiro.com/api/v2"
TIMEOUT = 20

STATUS_MESSAGES: dict[int, str] = {
    400: "API-то одби барањето (400). Проверете ги параметрите.",
    401: "Неавторизиран пристап до API-то (401). Проверете го API клучот.",
    403: "Пристапот до овој ресурс е забранет (403).",
    404: "Ресурсот не е достапен на API-то (404).",
    429: "Премногу барања до API-то (429). Почекајте пред следно освежување.",
    500: "Серверот на API-то врати внатрешна грешка (500).",
    502: "API-то е недостапно во моментот (502).",
    503: "API-то е привремено недостапно (503).",
}


TIMEOUT_MESSAGE = (
    "Барањето до API-то истече (timeout). Обидете се повторно за момент."
)
CONNECTION_MESSAGE = (
    "Нема конекција до серверот на API-то. Обидете се повторно."
)


def _network_label(error: Exception) -> str:
    """Кратка ознака за очекувани мрежни грешки (без stack trace)."""
    if isinstance(error, requests.Timeout):
        return "истечено време на барањето (timeout)"
    if isinstance(error, requests.ConnectionError):
        return "нема конекција"
    return type(error).__name__


RATE_LIMIT_STATUS = 429
# Внатрешен статус: клучот не е поставен (очекувана состојба, не е грешка).
MISSING_KEY_STATUS = -1
MISSING_KEY_MESSAGE = (
    "Не е поставен API клуч (BZZOIRO_API_KEY), па BZZ податоците не се "
    "вчитани. Апликацијата продолжува да работи без нив."
)
QUIET_STATUSES = (400, 404, 429)


class ApiError(Exception):
    """Грешка со порака подготвена за приказ на македонски."""

    def __init__(self, message: str, status: int = 0) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


def get_optional_dict(
    path: str, params: dict[str, str | int] | None = None
) -> tuple[dict, int]:
    """Тивко барање за подресурс (stats/h2h).

    Враќа (податоци, http статус). Никогаш не крева исклучок и не логира
    stack trace за очекувани 400/404/429 одговори — само кратка info линија.
    """
    if not has_api_key():
        logging.info(f"Подресурсот {path} е прескокнат: нема API клуч.")
        return {}, MISSING_KEY_STATUS
    headers = _headers()
    try:
        response = requests.get(
            f"{BASE_URL}{path}",
            headers=headers,
            params=params,
            timeout=TIMEOUT,
        )
    except requests.RequestException as error:
        # Очекувана мрежна состојба (timeout/нема конекција) — само кратка
        # безопасна info линија, без stack trace.
        logging.exception("Unexpected error")
        logging.info(
            f"Подресурсот {path} е недостапен: {_network_label(error)}"
        )
        return {}, 0

    if response.status_code == 200:
        try:
            data = response.json()
        except ValueError:
            logging.info(f"Подресурсот {path} врати невалиден JSON.")
            return {}, response.status_code
        return (data if isinstance(data, dict) else {}), 200

    if response.status_code in QUIET_STATUSES:
        logging.info(
            f"Подресурсот {path} не е достапен (HTTP {response.status_code})."
        )
    else:
        logging.warning(
            f"Подресурсот {path} врати HTTP {response.status_code}."
        )
    return {}, response.status_code


def get_list_soft(
    path: str, params: dict[str, str | int] | None = None
) -> tuple[list[dict], int]:
    """Тивко барање за листа. Враќа (редови, http статус).

    Никогаш не крева исклучок и не логира stack trace за очекувани
    400/404/429 одговори — само кратка info линија без чувствителни податоци.
    """
    if not has_api_key():
        logging.info(f"Ресурсот {path} е прескокнат: нема API клуч.")
        return [], MISSING_KEY_STATUS
    headers = _headers()
    try:
        response = requests.get(
            f"{BASE_URL}{path}",
            headers=headers,
            params=params,
            timeout=TIMEOUT,
        )
    except requests.RequestException as error:
        # Очекувана мрежна состојба — тивко, без stack trace.
        logging.exception("Unexpected error")
        logging.info(f"Ресурсот {path} е недостапен: {_network_label(error)}")
        return [], 0

    if response.status_code == 200:
        try:
            data = response.json()
        except ValueError:
            logging.info(f"Ресурсот {path} врати невалиден JSON.")
            return [], response.status_code
        if isinstance(data, dict):
            results = data.get("results")
            if isinstance(results, list):
                return [row for row in results if isinstance(row, dict)], 200
            return [], 200
        if isinstance(data, list):
            return [row for row in data if isinstance(row, dict)], 200
        return [], 200

    if response.status_code in QUIET_STATUSES:
        logging.info(
            f"Ресурсот {path} не е достапен (HTTP {response.status_code})."
        )
    else:
        logging.warning(f"Ресурсот {path} врати HTTP {response.status_code}.")
    return [], response.status_code


# Примарната променлива е BZZOIRO_API_KEY. Наследната BIZZOIRO се користи
# САМО како резерва за автентикација и никогаш не се логира/прикажува.
API_KEY_ENV_VARS: tuple[str, ...] = ("BZZOIRO_API_KEY", "BIZZOIRO")


def _api_key() -> str:
    """Го враќа првиот поставен клуч без да ја открие вредноста никаде."""
    for name in API_KEY_ENV_VARS:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def has_api_key() -> bool:
    return bool(_api_key())


def _headers() -> dict[str, str]:
    key = _api_key()
    if not key:
        raise ApiError(
            "Не е поставен API клуч (BZZOIRO_API_KEY) во околината.", 0
        )
    return {"Authorization": f"Token {key}", "Accept": "application/json"}


def get_json(
    path: str,
    params: dict[str, str | int] | None = None,
    allow_missing: bool = False,
) -> dict | list | None:
    """Прави GET барање и враќа JSON. Никогаш не логира заглавја/клучеви."""
    headers = _headers()
    url = f"{BASE_URL}{path}"
    try:
        response = requests.get(
            url, headers=headers, params=params, timeout=TIMEOUT
        )
    except requests.RequestException as error:
        logging.exception("Unexpected error")
        logging.info(f"Барањето кон {path} не успеа: {_network_label(error)}")
        raise ApiError(
            TIMEOUT_MESSAGE
            if isinstance(error, requests.Timeout)
            else CONNECTION_MESSAGE,
            0,
        ) from None

    if response.status_code == 200:
        try:
            return response.json()
        except ValueError as error:
            logging.info(f"Невалиден JSON од {path}: {error}")
            raise ApiError(
                "Неочекуван одговор од API-то (невалиден JSON).",
                response.status_code,
            ) from None

    if allow_missing and response.status_code in (400, 404):
        return None

    message = STATUS_MESSAGES.get(
        response.status_code,
        f"API-то врати грешка (HTTP {response.status_code}).",
    )
    if response.status_code in QUIET_STATUSES:
        logging.info(f"API одговор {response.status_code} за {path}.")
    else:
        logging.warning(
            f"API одговор {response.status_code} за {path} — {message}"
        )
    raise ApiError(message, response.status_code)


def get_list(
    path: str,
    params: dict[str, str | int] | None = None,
    allow_missing: bool = False,
) -> list[dict]:
    """Враќа `results` листа за пагинирани одговори или самата листа."""
    data = get_json(path, params=params, allow_missing=allow_missing)
    if data is None:
        return []
    if isinstance(data, dict):
        results = data.get("results")
        if isinstance(results, list):
            return [row for row in results if isinstance(row, dict)]
        return []
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    return []


def get_dict(
    path: str,
    params: dict[str, str | int] | None = None,
    allow_missing: bool = True,
) -> dict:
    data = get_json(path, params=params, allow_missing=allow_missing)
    return data if isinstance(data, dict) else {}
