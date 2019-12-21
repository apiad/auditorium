FROM python:3.6

WORKDIR /code
COPY pyproject.toml poetry.lock makefile /code/

ENV AUDITORIUM_ENVIRONMENT_DEV="true"
ENV XDG_CACHE_HOME="/opt/venv/cache"

RUN make install

COPY . /code

RUN poetry install
RUN make test

VOLUME [ "/opt/venv" ]
CMD bash
