"""Утилиты diff: применение unified diff к содержимому файла."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def apply_diff(original: str, diff_text: str) -> str:
    """Применить unified diff к исходному содержимому и вернуть результат.

    Raises:
        NotImplementedError: До тех пор, пока не подключена библиотека патчей.
    """
    logger.debug(
        "apply_diff: diff_len=%d original_len=%d",
        len(diff_text),
        len(original),
    )
    raise NotImplementedError("apply_diff ещё не реализован")
