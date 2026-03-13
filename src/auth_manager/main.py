from src.auth_manager.bootstrap import create_container


container = create_container()
app = container.fast_api_app().app
