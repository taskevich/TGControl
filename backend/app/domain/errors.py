class DomainError(Exception):
    pass


class InvalidInput(DomainError, ValueError):
    pass


class NotFound(DomainError):
    pass


class Conflict(DomainError):
    pass


class Gone(DomainError):
    pass


class AuthenticationFailed(DomainError):
    pass


class TooManyRequests(DomainError):
    pass


class OperationSkipped(DomainError):
    pass


class MediaTooLarge(OperationSkipped):
    def __init__(self, size: int, max_size: int):
        super().__init__(
            f"Файл {size / 2**20:.0f} МБ больше лимита {max_size / 2**20:.0f} МБ"
        )
        self.size = size


class AccountUnavailable(Conflict):
    pass


class TelegramError(DomainError):
    pass


class FloodWait(TooManyRequests, TelegramError):
    def __init__(self, seconds: int):
        super().__init__(f"FloodWait: подождать {seconds} с")
        self.seconds = seconds


class AccountDead(TelegramError):
    def __init__(self, message: str, *, banned: bool, name: str):
        super().__init__(message)
        self.banned = banned
        self.name = name


class PasswordRequired(TelegramError):
    def __init__(self, session: str):
        super().__init__("Требуется пароль 2FA")
        self.session = session


class InvalidPassword(TelegramError):
    pass


class InvalidCode(TelegramError):
    pass
