from src.auth_manager.components.exceptions.abstract import AbstractApplicationException


class BadRequestException(AbstractApplicationException):
    """Класс ошибки некорректного запроса"""

    def __init__(
        self,
        name: str = f"{AbstractApplicationException.app_domain}.general.bad-request",
    ):
        super().__init__(code="400", name=name)
