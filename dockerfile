# =====================
# Generic build system
# ---------------------

ARG PYTHON_VERSION
FROM python:${PYTHON_VERSION}

# Install yarn and now
RUN if [ "${PYTHON_VERSION}" == "3.8" ] ; then \
    curl -sS https://dl.yarnpkg.com/debian/pubkey.gpg | apt-key add - && \
    echo "deb https://dl.yarnpkg.com/debian/ stable main" | tee /etc/apt/sources.list.d/yarn.list && \
    apt update && \
    apt install -y yarn && \
    yarn global add now ; \
    fi

# ==========================================
# Project-specific installation instruction
# ------------------------------------------

WORKDIR /code
COPY pyproject.toml poetry.lock makefile /code/

ENV BUILD_ENVIRONMENT="development"
ENV XDG_CACHE_HOME="/opt/dev/cache"

# Use system's Python for installing dev tools
RUN make dev-install

COPY . /code

VOLUME [ "/opt/dev" ]
CMD [ "bash" ]
