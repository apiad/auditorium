.PHONY: clean lint test test-full shell

shell:
	docker-compose run auditorium bash

build:
	docker-compose run auditorium make dev-build

clean:
	git clean -fxd

lint:
	docker-compose run auditorium poetry run pylint auditorium

test:
	docker-compose run auditorium make dev-test-simple

test-full:
	docker-compose run auditorium make dev-test-full

# Below are the commands that will be run INSIDE the development environment, i.e., inside Docker or Travis
# These commands are NOT supposed to be run by the developer directly, and will fail to do so.

.PHONY: dev-build clean dev-install dev-test dev-cov dev-ensure

dev-ensure:
	# Check if you are inside a development environment
	echo ${BUILD_ENVIRONMENT} | grep "development" >> /dev/null

dev-build: dev-ensure
	poetry build

dev-install: dev-ensure
	pip install poetry
	pip install tox
	poetry config virtualenvs.create false

dev-install-deps: dev-ensure
	poetry install

dev-test-full: dev-ensure
	tox

dev-test-simple: dev-ensure
	python -m mypy -p auditorium --ignore-missing-imports
	python -m pytest --doctest-modules --cov=auditorium --cov-report=term-missing -v

dev-test-single: dev-ensure
	python -m auditorium test
	python -m mypy -p auditorium --ignore-missing-imports
	python -m pytest --doctest-modules --cov=auditorium --cov-report=xml

dev-cov: dev-ensure
	python -m codecov
