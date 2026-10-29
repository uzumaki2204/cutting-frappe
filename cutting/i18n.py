"""One UTF-8 catalog for API, installer and tablet messages."""

import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def catalog():
    return json.loads((Path(__file__).parent / "i18n.json").read_text(encoding="utf-8"))


def message(key, lang=None, **values):
    if lang is None:
        try:
            import frappe
            lang = getattr(frappe.local, "lang", None)
        except (ImportError, AttributeError):
            lang = None
    language = (lang or "vi").split("-")[0]
    entries = catalog()
    template = entries.get(language, entries["vi"]).get(key, entries["vi"].get(key, entries["vi"]["error.unexpected"]))
    return template.format(**values)
