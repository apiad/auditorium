.PHONY: build clean install test

build:
	pip install pipenv
	pipenv run python setup.py sdist bdist_wheel

clean:
	git clean -fxd

install:
	pipenv install --dev --skip-lock

test:
	pipenv run pytest --doctest-modules --cov=python_starter_pack --cov-report=xml -v

cov:
	pipenv run codecov
