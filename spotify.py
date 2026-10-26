"""Голосовые команды настольного Spotify через медиасессии Windows, без API-ключей."""
from dataclasses import dataclass
import logging
import os
import re
import time
from urllib.parse import quote

import media


log = logging.getLogger("capri")
NAME = r"(?:spotify|споти\s*ф(?:ай|ае|аи|ая))"
NAME_RE = re.compile(rf"\b{NAME}\b", re.IGNORECASE)


@dataclass
class Command:
    action: str
    query: str = ""


@dataclass
class Result:
    text: str
    selected: bool = False


def has_name(text):
    return bool(NAME_RE.search(text))


def parse_command(text, implicit=False):
    """Только явные команды Spotify либо короткие команды после его выбора."""
    explicit = has_name(text)
    if not (explicit or implicit):
        return None
    text = text.lower().replace("ё", "е").strip(" .,!?")
    if explicit:
        text = re.sub(rf"\b(?:(?:в|на|из)\s+)?{NAME}\b", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" .,!?")
    if explicit and text in ("", "открой", "запусти"):
        return Command("open")
    patterns = (
        ("pause", r"(?:пауза|(?:поставь|поставить) (?:музыку )?на паузу|на паузу|"
                  r"(?:останови|остановить|выключи|выключить|стоп)(?: (?:музыку|трек|песню))?)"),
        ("next", r"(?:(?:включи|поставь|давай|переключи(?: на)?) )?следующ\w*(?: (?:трек|песн\w*))?|"
                 r"(?:дальше|скипни|пропусти)(?: (?:трек|песн\w*))?|переключи(?: (?:трек|песн\w*))?"),
        ("prev", r"(?:(?:включи|поставь|верни|давай|переключи(?: на)?) )?(?:предыдущ|прошл)\w*"
                 r"(?: (?:трек|песн\w*))?"),
        ("info", r"что (?:сейчас )?(?:играет|звучит)|что за (?:песня|трек|музыка)"),
        ("play", r"(?:продолжи|продолжай|играй|воспроизведи)(?: (?:музыку|трек|песню))?|"
                 r"сними(?: с)? пауз\w*|(?:включи|включить|запусти|поставь|поставить)"
                 r"(?: мне)?(?: (?:музыку|трек|песню|плейлист))?(?: (?:обратно|снова|дальше))?|музыка"),
    )
    for action, pattern in patterns:
        if re.fullmatch(pattern, text):
            return Command(action)
    # Именованные запросы открываем именно в Spotify, а не на YouTube.
    # Поиск сам по себе не гарантирует воспроизведение: это честно сообщаем в ответе.
    if explicit:
        match = re.fullmatch(r"(?:включи|поставь|найди|поищи) (?:мне )?"
                             r"(?:(?:песню|трек|музыку|плейлист) )?(.+)", text)
        if match:
            return Command("search", match.group(1))
    return None


def _launch(uri="spotify:"):
    try:
        os.startfile(uri)
        return True
    except (OSError, AttributeError):
        log.exception("Не удалось открыть Spotify")
        return False


def _wait_session(timeout=8):
    deadline = time.monotonic() + timeout
    while True:
        info = media.now_playing(source="spotify")
        if info is not None or time.monotonic() >= deadline:
            return info
        time.sleep(0.2)


def execute(command):
    """Управляем только Spotify. Пауза/переключение не запускают закрытое приложение."""
    if command.action in ("open", "search"):
        uri = "spotify:search:" + quote(command.query, safe="") if command.action == "search" else "spotify:"
        if not _launch(uri):
            return Result("Не смогла открыть Spotify. Проверь, что установлено настольное приложение.")
        if command.action == "search":
            return Result(f"Открыла поиск «{command.query}» в Spotify. Выбери нужный трек в приложении.", True)
        return Result("Открыла Spotify.", True)
    try:
        info = media.now_playing(source="spotify")
        if info is None and command.action == "play":
            if not _launch():
                return Result("Не смогла открыть Spotify. Проверь, что установлено настольное приложение.")
            info = _wait_session()
        if info is None:
            return Result("Не вижу плеер Spotify. Открой приложение, войди в аккаунт и выбери трек один раз.")
        if command.action == "info":
            return Result(f"В Spotify: {info[0]}." if info[0] else "Spotify пока не сообщил название трека.", True)
        if command.action == "pause" and not info[2]:
            return Result("Музыка в Spotify уже на паузе.", True)
        if command.action == "play" and info[2]:
            return Result("Музыка в Spotify уже играет.", True)
        ok, _, _ = media.control(command.action, source="spotify")
        if not ok:
            return Result("Spotify не выполнил команду. Проверь очередь и доступность управления в приложении.")
        messages = {"play": "Включила музыку в Spotify.", "pause": "Музыка в Spotify на паузе.",
                    "next": "Следующий трек в Spotify.", "prev": "Предыдущий трек в Spotify."}
        return Result(messages[command.action], True)
    except Exception:
        log.exception("Ошибка управления Spotify")
        return Result("Не удалось связаться с плеером Spotify. Проверь приложение и повтори команду.")
