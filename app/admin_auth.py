import os
import secrets

from dotenv import load_dotenv


load_dotenv()


_MINIMUM_TOKEN_LENGTH = 32

_ADMIN_API_TOKEN = os.getenv(
    "ADMIN_API_TOKEN",
    "",
).strip()


def admin_token_is_configured() -> bool:
    """检查管理员密钥是否已正确配置。"""

    return (
        len(_ADMIN_API_TOKEN)
        >= _MINIMUM_TOKEN_LENGTH
    )


def verify_admin_authorization(
    authorization: str | None,
) -> bool:
    """验证Authorization请求头中的Bearer密钥。"""

    if not admin_token_is_configured():
        return False

    if not isinstance(authorization, str):
        return False

    scheme, separator, token = (
        authorization.strip().partition(" ")
    )

    if (
        not separator
        or scheme.lower() != "bearer"
    ):
        return False

    normalized_token = token.strip()

    if not normalized_token:
        return False

    return secrets.compare_digest(
        normalized_token,
        _ADMIN_API_TOKEN,
    )