import base64
import hashlib
import hmac
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from cryptography.fernet import Fernet, InvalidToken

from app.application.ports.services import TokenClaims
from app.domain.errors import AuthenticationFailed, InvalidInput

ALGORITHM = "HS256"


class BcryptHasher:
    def hash(self, password: str) -> str:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    def verify(self, password: str, password_hash: str) -> bool:
        try:
            return bcrypt.checkpw(password.encode(), password_hash.encode())
        except ValueError:
            return False


class JwtTokenService:
    def __init__(self, secret: str, ttl_minutes: int):
        self._secret = secret
        self._ttl = timedelta(minutes=ttl_minutes)

    def issue(self, subject: str) -> tuple[str, int]:
        payload = {
            "sub": subject,
            "jti": uuid.uuid4().hex,
            "exp": datetime.now(timezone.utc) + self._ttl,
        }
        return jwt.encode(payload, self._secret, algorithm=ALGORITHM), int(
            self._ttl.total_seconds()
        )

    def decode(self, token: str) -> TokenClaims:
        try:
            payload = jwt.decode(token, self._secret, algorithms=[ALGORITHM])
        except jwt.PyJWTError as e:
            raise AuthenticationFailed("Недействительный токен") from e
        return TokenClaims(
            subject=payload.get("sub"),
            token_id=payload.get("jti"),
            expires_at=payload["exp"],
        )


class FernetCipher:
    def __init__(self, key: str, secret_key: str):
        if not key:
            key = base64.urlsafe_b64encode(
                hashlib.sha256(secret_key.encode()).digest()
            ).decode()
        self._fernet = Fernet(key)

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode()).decode()

    def decrypt(self, value: str) -> str:
        try:
            return self._fernet.decrypt(value.encode()).decode()
        except InvalidToken as e:
            raise InvalidInput(
                "Не удалось расшифровать сессию: изменён SECRET_KEY/SESSION_ENCRYPTION_KEY?"
            ) from e


def generate_key() -> str:
    return Fernet.generate_key().decode()


class HmacSigner:
    def __init__(self, secret: str, purpose: str = "media"):
        self._key = hashlib.sha256(f"{purpose}:{secret}".encode()).digest()

    def sign(self, value: str) -> str:
        return hmac.new(self._key, value.encode(), hashlib.sha256).hexdigest()[:32]

    def verify(self, value: str, signature: str) -> bool:
        return hmac.compare_digest(self.sign(value), signature or "")
