"""Тивко филтрирање на шумни трети-страни логови (без криење реални грешки).

Fotmob библиотеката печати повторливи пораки за недостапен „x-mas token“
(HTTP 404) што не влијаат на апликацијата. Тие се исклучуваат САМО ако
пораката содржи и „x-mas“/„xmas“ и „404“; сите останати пораки, вклучувајќи
вистинските грешки на апликацијата, остануваат непроменети.
"""

import logging

_NOISE_TOKENS: tuple[str, ...] = ("x-mas", "xmas", "x_mas")
_INSTALLED = False


class _FotmobTokenNoiseFilter(logging.Filter):
    """Исклучува само познатиот 404 шум за x-mas токенот."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno >= logging.ERROR:
            return True
        try:
            message = record.getMessage().lower()
        except Exception:
            logging.exception("Unexpected error")
            return True
        if "404" not in message:
            return True
        return not any(token in message for token in _NOISE_TOKENS)


def install_fotmob_log_filter() -> None:
    """Го поставува филтерот еднаш, на root и на fotmob логерите."""
    global _INSTALLED
    if _INSTALLED:
        return
    noise_filter = _FotmobTokenNoiseFilter()
    for name in ("", "fotmob", "fotmob_api", "FotMob"):
        logging.getLogger(name).addFilter(noise_filter)
    for handler in logging.getLogger().handlers:
        handler.addFilter(noise_filter)
    _INSTALLED = True
