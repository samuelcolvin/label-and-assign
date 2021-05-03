.DEFAULT_GOAL := lint
isort = isort main.py
black = black -S -l 120 --target-version py38 main.py

.PHONY: install
install:
	pip install -U -r requirements.txt
	pip install -U black isort flake8

.PHONY: format
format:
	$(isort)
	$(black)

.PHONY: lint
lint:
	flake8 main.py
	$(isort) --check-only --df
	$(black) --check --diff
