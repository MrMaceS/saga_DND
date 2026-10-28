from fastapi import Header, Query

from app.domain.errors import SagaError


def table_token_from(x_table_token: str | None = Header(default=None), table_token: str | None = Query(default=None)) -> str:
    token = x_table_token or table_token
    if not token:
        raise SagaError("unauthorized", "Нужен токен Стола")
    return token
