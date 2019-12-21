FROM python:3.6

WORKDIR /code
COPY pyproject.toml poetry.lock makefile /code/

ENV AUDITORIUM_ENVIRONMENT="development"
ENV XDG_CACHE_HOME="/opt/venv/cache"

RUN make dev-install

COPY . /code

VOLUME [ "/opt/venv" ]
CMD bash
