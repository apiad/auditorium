.PHONY: build clean install test lint cov

# TODO: Update your project folder
PROJECT=auditorium

build:
	poetry build

clean:
	git clean -fxd

install-base:
	pip install -U pip
	pip install poetry

install-bare: install-base
	poetry config virtualenvs.create false
	poetry install

install: install-base
	poetry install

test:
	poetry run auditorium test && \
	poetry run mypy -p auditorium --ignore-missing-imports && \
	poetry run pytest --doctest-modules --cov=$(PROJECT) --cov-report=xml -v

lint:
	poetry run pylint $(PROJECT)

cov:
	poetry run codecov
