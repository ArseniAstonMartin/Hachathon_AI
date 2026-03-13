from src.auth_manager.components.fast_api_app import FastApiApp
from src.auth_manager.domains import DOMAIN_DESCRIPTORS


class ApiRuntime:
    def __init__(self, application: FastApiApp):
        self._application = application
        self._domains = tuple(
            descriptor for descriptor in DOMAIN_DESCRIPTORS if descriptor.layer == "api"
        )

    @property
    def app(self):
        return self._application.app

    @property
    def domains(self):
        return self._domains
