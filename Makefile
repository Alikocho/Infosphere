.PHONY: install test lint run serve smoke build clean

install:
	pip install -e ".[all]"
	pip install -r requirements-dev.txt

test:
	python -m pytest tests/ -v

coverage:
	python -m pytest tests/ --cov=infosphere --cov-report=term-missing

lint:
	flake8 infosphere/ --select=E9,F63,F7,F82 --show-source

run:
	python main.py --scenario election

smoke:
	python main.py --scenario election --quiet
	python main.py --scenario alliance --quiet
	python main.py --scenario health   --quiet
	@echo "All scenarios passed."

serve:
	python server.py --human red --scenario election

serve-pvp:
	python server.py --human both --scenario alliance

build:
	pip install build
	python -m build

clean:
	rm -rf dist/ build/ *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
