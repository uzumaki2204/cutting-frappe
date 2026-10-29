import json

from cutting import __version__
from cutting.i18n import catalog, message


def get_context(context):
    import frappe

    lang = str(frappe.form_dict.get("lang") or "vi").split("-")[0]
    context.no_cache = 1
    context.title = message("ui.title", lang=lang)
    context.lang = lang if lang in catalog() else "vi"
    context.texts = catalog()[context.lang]
    context.texts_json = json.dumps(context.texts, ensure_ascii=False)
    context.asset_version = __version__
