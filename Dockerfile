FROM python:3.11

RUN curl -sSL https://install.python-poetry.org | python3 - && \
    ln -s /root/.local/bin/poetry /usr/local/bin/poetry

RUN apt-get update && apt-get install -y netcat-openbsd && rm -rf /var/lib/apt/lists/*

WORKDIR /fastapi_auth_service

COPY pyproject.toml poetry.lock* ./

RUN poetry config virtualenvs.create false && \
    poetry install --no-root # можно указать --only main если не нужны тесты

COPY . .

EXPOSE 8000

CMD poetry run uvicorn src.auth_manager.main:app --host 0.0.0.0 --port 1000
