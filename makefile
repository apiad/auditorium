.PHONY: build clean install test lint cov

# TODO: Update your project folder
PROJECT=auditorium

build:
	poetry build

clean:
	git clean -fxd

install:
	curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python
	poetry install

test:
	poetry run pytest --doctest-modules --cov=$(PROJECT) --cov-report=xml -v

lint:
	poetry run pylint $(PROJECT)

cov:
	poetry run codecov
