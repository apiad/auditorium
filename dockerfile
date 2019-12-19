FROM python:3.6

WORKDIR /code
COPY pyproject.toml poetry.lock makefile /code/

ENV XDG_CACHE_HOME="/opt/venv/cache"
ENV POETRY_VIRTUALENVS_PATH="/opt/venv"

RUN make install-bare

COPY . /code

RUN poetry install
RUN make test

VOLUME [ "/opt/venv" ]
CMD bash
