.PHONY: clean lint test-fast test-full shell docs docker-build docker-push

BASE_VERSION := 3.8
ALL_VERSIONS := 3.6 3.7 3.8

test-fast:
	PYTHON_VERSION=${BASE_VERSION} docker-compose run auditorium-dev make dev-test-fast

docs-serve:
	PYTHON_VERSION=${BASE_VERSION} docker-compose run auditorium-dev mkdocs serve

docs-deploy:
	PYTHON_VERSION=${BASE_VERSION} docker-compose run auditorium-dev mkdocs gh-deploy && cp docs/index.md Readme.md

shell:
	PYTHON_VERSION=${BASE_VERSION} docker-compose run auditorium-dev bash

lock:
	PYTHON_VERSION=${BASE_VERSION} docker-compose run auditorium-dev poetry lock

build:
	PYTHON_VERSION=${BASE_VERSION} docker-compose run auditorium-dev poetry build

clean:
	git clean -fxd

lint:
	PYTHON_VERSION=${BASE_VERSION} docker-compose run auditorium-dev poetry run pylint auditorium

test-full:
	$(foreach VERSION, $(ALL_VERSIONS), PYTHON_VERSION=${VERSION} docker-compose up;)

docker-build:
	$(foreach VERSION, $(ALL_VERSIONS), PYTHON_VERSION=${VERSION} docker-compose build auditorium-dev;)

docker-push:
	$(foreach VERSION, $(ALL_VERSIONS), PYTHON_VERSION=${VERSION} docker-compose push;)

# Below are the commands that will be run INSIDE the development environment, i.e., inside Docker or Travis
# These commands are NOT supposed to be run by the developer directly, and will fail to do so.

.PHONY: dev-ensure dev-build dev-install dev-test-fast dev-test-full dev-cov

dev-ensure:
	# Check if you are inside a development environment
	echo ${BUILD_ENVIRONMENT} | grep "development" >> /dev/null

dev-install: dev-ensure
	pip install poetry
	poetry config virtualenvs.create false
	poetry install -E server

dev-test-fast: dev-ensure
	python -m mypy -p auditorium --ignore-missing-imports
	python -m pytest --doctest-modules --cov=auditorium --cov-report=term-missing -v

dev-test-full: dev-ensure
	python -m auditorium test
	python -m mypy -p auditorium --ignore-missing-imports
	python -m pytest --doctest-modules --cov=auditorium --cov-report=xml

dev-cov: dev-ensure
	python -m codecov
