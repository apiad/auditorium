.PHONY: clean lint test-fast test-full shell

BASE_VERSION := 3.8
ALL_VERSIONS := 3.6 3.7 3.8

test-fast:
	PYTHON_VERSION=${BASE_VERSION} docker-compose run auditorium-tester make dev-test-fast

shell:
	PYTHON_VERSION=${BASE_VERSION} docker-compose run auditorium-tester bash

build:
	PYTHON_VERSION=${BASE_VERSION} docker-compose run auditorium-tester make dev-build

clean:
	git clean -fxd

lint:
	PYTHON_VERSION=${BASE_VERSION} docker-compose run auditorium-tester poetry run pylint auditorium

test-full:
	$(foreach VERSION, $(ALL_VERSIONS), PYTHON_VERSION=${VERSION} docker-compose up;)

docker-build:
	$(foreach VERSION, $(ALL_VERSIONS), PYTHON_VERSION=${VERSION} docker-compose build;)

docker-push:
	$(foreach VERSION, $(ALL_VERSIONS), PYTHON_VERSION=${VERSION} docker-compose push;)

# Below are the commands that will be run INSIDE the development environment, i.e., inside Docker or Travis
# These commands are NOT supposed to be run by the developer directly, and will fail to do so.

.PHONY: dev-ensure dev-build dev-install dev-test-fast dev-test-full dev-cov

dev-ensure:
	# Check if you are inside a development environment
	echo ${BUILD_ENVIRONMENT} | grep "development" >> /dev/null

dev-build: dev-ensure
	poetry build

dev-install: dev-ensure
	pip install poetry
	poetry config virtualenvs.create false
	poetry install

dev-test-fast: dev-ensure
	python -m mypy -p auditorium --ignore-missing-imports
	python -m pytest --doctest-modules --cov=auditorium --cov-report=term-missing -v

dev-test-full: dev-ensure
	python -m auditorium test
	python -m mypy -p auditorium --ignore-missing-imports
	python -m pytest --doctest-modules --cov=auditorium --cov-report=xml

dev-cov: dev-ensure
	python -m codecov
