import asyncio

from src.auth_manager.bootstrap import create_container


async def _run_worker() -> None:
    container = create_container()
    await container.worker_runtime().run()


def main() -> None:
    try:
        asyncio.run(_run_worker())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
