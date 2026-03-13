from src.auth_manager.components.register_modules import register_modules
from src.auth_manager.di import DependencyInjector


def create_container() -> DependencyInjector:
    register_modules(
        package_name="src",
        container=DependencyInjector,
    )
    container = DependencyInjector()
    container.wire(packages=["src"])
    return container
