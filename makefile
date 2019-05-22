.PHONY: build clean install test

build:
	pipenv run python setup.py sdist bdist_wheel

clean:
	git clean -fxd

install:
	pip install pipenv
	pipenv install --dev --skip-lock

test:
	pipenv run pylint python_starter_pack && pytest --doctest-modules --cov=python_starter_pack --cov-report=xml -v

cov:
	pipenv run codecov
