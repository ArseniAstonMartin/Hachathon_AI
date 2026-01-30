from src.auth_manager.components.exceptions.abstract import AbstractApplicationException


class ForbiddenException(AbstractApplicationException):
    """Класс ошибки прав доступа"""

    def __init__(self):
        super().__init__(code="403", name=f"{self.app_domain}.general.forbidden")
