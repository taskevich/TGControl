import asyncio
import sys

from app.container import build_container
from app.domain.errors import DomainError
from app.infrastructure.config import settings
from app.infrastructure.security import generate_key


async def _set_password(username: str, password: str, create: bool) -> None:
    container = build_container(settings)
    try:
        await container.users.set_password(username, password, create=create)
    except DomainError as e:
        sys.exit(str(e))
    finally:
        await container.close()
    print(f"OK: {username}")


def main() -> None:
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    cmd = args[0]
    if cmd == "gen-key":
        print(generate_key())
    elif cmd in ("create-user", "set-password") and len(args) == 3:
        asyncio.run(_set_password(args[1], args[2], create=cmd == "create-user"))
    else:
        sys.exit(__doc__)
