.PHONY: build clean install test lint cov environment

is-dev:
	echo ${AUDITORIUM_ENVIRONMENT} | grep "development" >> /dev/null

build: is-dev
	poetry build

clean:
	git clean -fxd

install: is-dev
	pip install -U pip
	pip install poetry
	pip install tox
	poetry config virtualenvs.create false
	poetry install

test: is-dev
	tox

lint: is-dev
	poetry run pylint auditorium

cov: is-dev
	poetry run codecov
