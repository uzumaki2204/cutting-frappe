"""Register the Cutting Summary API in Desk Swagger during Pilot migrate."""


def execute():
    from cutting.api_docs import ensure_catalog

    ensure_catalog()
