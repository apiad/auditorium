# =====================
# Generic build system
# ---------------------

FROM python:3-slim

# Install pre-requisites for building Python with pyenv-installer
# https://github.com/pyenv/pyenv/wiki/Common-build-problems

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && \
    apt-get install -yq make build-essential libssl-dev zlib1g-dev libbz2-dev \
    libreadline-dev libsqlite3-dev wget curl llvm libncurses5-dev libncursesw5-dev \
    xz-utils tk-dev libffi-dev liblzma-dev python-openssl git

# Install pyenv with pyenv-installer
# https://github.com/pyenv/pyenv-installer

ENV PYENV_ROOT=/opt/dev/pyenv
ENV PATH=/opt/dev/pyenv/bin:$PATH
RUN curl https://pyenv.run | bash

# Install Python versions
# Add here the exact versions of Python you're developing for

RUN pyenv install 3.6.10
RUN pyenv install 3.7.6
RUN pyenv install 3.8.1

# This makes pyenv shims visible
ENV PATH=$PYENV_ROOT/shims:$PATH

# ==========================================
# Project-specific installation instruction
# ------------------------------------------

WORKDIR /code
COPY pyproject.toml poetry.lock makefile /code/

ENV BUILD_ENVIRONMENT="development"
ENV XDG_CACHE_HOME="/opt/dev/cache"

# Use system's Python for installing dev tools
RUN pyenv global system
RUN make dev-install

COPY . /code

VOLUME [ "/opt/dev" ]
CMD [ "bash" ]
