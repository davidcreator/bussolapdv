PYTHON ?= python3
export QT_QPA_PLATFORM ?= offscreen
export PYTHONPATH := src

.PHONY: ajuda instalar test test-rapido lint tipos capturas responsivo demo ui backup limpar

ajuda:
	@echo "make instalar  - cria venv e instala dependências de desenvolvimento"
	@echo "make test      - executa a suíte completa (Qt offscreen)"
	@echo "make lint      - ruff"
	@echo "make tipos     - mypy"
	@echo "make demo      - cria base fictícia em dados/demo.db"
	@echo "make ui        - abre a interface na base de demonstração"
	@echo "make capturas  - gera docs/capturas/*.png sem servidor gráfico"
	@echo "make responsivo- mede a interface em 800×600 até 1920×1080 e aponta o que estoura"
	@echo "make limpar    - remove caches"

instalar:
	$(PYTHON) -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest tests -q

test-rapido:
	$(PYTHON) -m pytest tests -q -m "not ui"

lint:
	$(PYTHON) -m ruff check src tests

tipos:
	$(PYTHON) -m mypy

demo:
	$(PYTHON) -m bussola_pdv.cli demo --banco dados/demo.db --forcar

ui: demo
	$(PYTHON) -m bussola_pdv.cli ui --banco dados/demo.db

backup:
	$(PYTHON) -m bussola_pdv.cli backup --banco dados/demo.db --destino copias/

capturas:
	$(PYTHON) ferramentas/captura_telas.py

responsivo:
	$(PYTHON) ferramentas/verificar_responsivo.py

limpar:
	rm -rf .pytest_cache .ruff_cache .mypy_cache __pycache__ */__pycache__ */*/__pycache__ */*/*/__pycache__
	rm -rf build dist *.egg-info .coverage htmlcov
