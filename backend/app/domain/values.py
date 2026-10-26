import re
from dataclasses import dataclass
from urllib.parse import parse_qs, quote, unquote, urlparse

from app.domain.errors import InvalidInput

CHANNEL_ID_SHIFT = 1_000_000_000_000


def split_peer_id(marked_id: int) -> tuple[int, str]:
    if marked_id >= 0:
        return marked_id, "user"
    real = -marked_id
    if real > CHANNEL_ID_SHIFT:
        return real - CHANNEL_ID_SHIFT, "channel"
    return real, "chat"


def tme_link(username: str | None, chat_id: int, msg_id: int) -> str | None:
    if username:
        return f"https://t.me/{username}/{msg_id}"
    real_id, kind = split_peer_id(chat_id)
    if kind == "channel":
        return f"https://t.me/c/{real_id}/{msg_id}"
    return None


def comment_link(parent_link: str | None, msg_id: int) -> str | None:
    if not parent_link:
        return None
    return f"{parent_link.split('?')[0]}?comment={msg_id}"


TME_RE = re.compile(r"^(?:https?://)?(?:www\.)?(?:t|telegram)\.(?:me|dog)/(.+)$", re.I)
USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{3,31}$")


@dataclass
class Target:
    kind: str  # username | invite | id | public_msg | private_msg
    raw: str
    username: str | None = None
    invite_hash: str | None = None
    peer_id: int | None = None
    msg_id: int | None = None
    comment_id: int | None = None

    @classmethod
    def by_id(cls, peer_id: int) -> "Target":
        return cls("id", str(peer_id), peer_id=peer_id)

    @property
    def is_message_link(self) -> bool:
        return self.kind in ("public_msg", "private_msg")


def parse_target(raw: str) -> Target:
    s = (raw or "").strip()
    if not s:
        raise InvalidInput("Пустая цель")
    if re.fullmatch(r"-?\d+", s):
        return Target("id", s, peer_id=int(s))
    if s.startswith("@"):
        return Target("username", s, username=s[1:])
    if s.lower().startswith("tg://"):
        _, _, query = s.partition("?")
        qs = parse_qs(query)
        if "domain" in qs:
            return Target("username", s, username=qs["domain"][0])
        if "invite" in qs:
            return Target("invite", s, invite_hash=qs["invite"][0])
        raise InvalidInput(f"Не удалось распознать ссылку: {raw}")

    m = TME_RE.match(s)
    if m:
        path, _, query = m.group(1).partition("?")
        qs = parse_qs(query)
        parts = [p for p in path.split("/") if p]
        if not parts:
            raise InvalidInput(f"Не удалось распознать ссылку: {raw}")
        if parts[0].startswith("+"):
            return Target("invite", s, invite_hash=parts[0][1:])
        if parts[0] == "joinchat" and len(parts) > 1:
            return Target("invite", s, invite_hash=parts[1])
        if parts[0] == "s" and len(parts) > 1:
            parts = parts[1:]
        comment = (
            int(qs["comment"][0])
            if "comment" in qs and qs["comment"][0].isdigit()
            else None
        )
        if parts[0] == "c" and len(parts) >= 2 and parts[1].isdigit():
            peer_id = int(f"-100{parts[1]}")
            if len(parts) >= 3 and parts[-1].isdigit():
                return Target(
                    "private_msg",
                    s,
                    peer_id=peer_id,
                    msg_id=int(parts[-1]),
                    comment_id=comment,
                )
            return Target("id", s, peer_id=peer_id)
        username = parts[0]
        if len(parts) >= 2 and parts[-1].isdigit():
            return Target(
                "public_msg",
                s,
                username=username,
                msg_id=int(parts[-1]),
                comment_id=comment,
            )
        return Target("username", s, username=username)

    if USERNAME_RE.match(s):
        return Target("username", s, username=s)
    raise InvalidInput(f"Не удалось распознать цель: {raw}")


PROXY_SCHEMES = ("socks5", "socks4", "http")


@dataclass(frozen=True)
class ProxyAddress:
    scheme: str
    host: str
    port: int
    username: str | None = None
    password: str | None = None

    @classmethod
    def parse(cls, raw: str | None) -> "ProxyAddress":
        if not raw or not raw.strip():
            raise InvalidInput("Пустой прокси")
        raw = raw.strip()
        try:
            if "://" in raw:
                u = urlparse(raw)
                scheme, host, port = u.scheme.lower(), u.hostname, u.port
                user = unquote(u.username) if u.username else None
                password = unquote(u.password) if u.password else None
            else:
                parts = raw.split(":")
                if len(parts) < 2:
                    raise InvalidInput(f"Неверный формат прокси: {raw}")
                scheme, host, port = "socks5", parts[0], int(parts[1])
                user = parts[2] if len(parts) > 2 else None
                password = parts[3] if len(parts) > 3 else None
        except InvalidInput:
            raise
        except ValueError as e:
            raise InvalidInput(f"Неверный формат прокси: {raw}") from e
        if scheme not in PROXY_SCHEMES:
            raise InvalidInput(f"Неподдерживаемый тип прокси: {scheme}")
        if not host or not port:
            raise InvalidInput(f"Неверный формат прокси: {raw}")
        return cls(scheme, host, int(port), user or None, password or None)

    def url(self, mask: bool = False) -> str:
        auth = ""
        if self.username:
            pwd = "***" if mask else quote(self.password or "", safe="")
            auth = f"{quote(self.username, safe='')}:{pwd}@"
        return f"{self.scheme}://{auth}{self.host}:{self.port}"


NEW_PASSWORD_MIN_LENGTH = 12


def check_new_account_password(password: str) -> str:
    if len(password) < NEW_PASSWORD_MIN_LENGTH:
        raise InvalidInput(
            f"Пароль должен быть не короче {NEW_PASSWORD_MIN_LENGTH} символов"
        )
    return password


def normalize_phone(raw: str) -> str:
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) < 7:
        raise InvalidInput("Некорректный номер телефона")
    return "+" + digits
