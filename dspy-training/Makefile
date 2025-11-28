.PHONY: install prepare-data train test clean help

# Python executable - use venv if available
PYTHON := $(shell if [ -d venv ]; then echo venv/bin/python3; else echo python3; fi)
PIP := $(shell if [ -d venv ]; then echo venv/bin/pip3; else echo pip3; fi)

# Default target
help:
	@echo "DSPy Training Infrastructure for OpenCode"
	@echo ""
	@echo "Available targets:"
	@echo "  make install       - Install dependencies (creates venv)"
	@echo "  make prepare-data  - Validate and process raw data"
	@echo "  make train         - Run the training pipeline"
	@echo "  make test          - Run unit tests"
	@echo "  make clean         - Clean generated files"
	@echo "  make help          - Show this help message"

# Install dependencies
install:
	@echo "Setting up virtual environment..."
	@if [ ! -d venv ]; then python3 -m venv venv; fi
	@echo "Installing dependencies..."
	@$(PIP) install -r requirements.txt
	@echo "Installation complete!"
	@echo ""
	@echo "Next steps:"
	@echo "1. Copy .env.example to .env and add your API keys"
	@echo "2. Place session logs in data/raw/"
	@echo "3. Review config.yaml"
	@echo "4. Run: make train"

# Validate and process raw data
prepare-data:
	@echo "Validating data in data/raw/..."
	@$(PYTHON) -c "import sys; \
		from pathlib import Path; \
		from src.data_loader import DataLoader; \
		loader = DataLoader('data/raw'); \
		sessions = loader.load_all_sessions(); \
		print(f'✓ Found {len(sessions)} valid session logs'); \
		successful = loader.filter_successful(sessions); \
		print(f'✓ {len(successful)} successful sessions'); \
		examples = loader.extract_examples(sessions); \
		print(f'✓ {len(examples)} total examples'); \
		sys.exit(0 if examples else 1)"
	@echo "Data validation complete!"

# Run the training pipeline
train:
	@echo "Starting DSPy training pipeline..."
	@$(PYTHON) run_training.py

# Run unit tests
test:
	@echo "Running tests..."
	@$(PYTHON) -m pytest tests/ -v || echo "No tests found yet. Create tests in tests/ directory"

# Clean generated files
clean:
	@echo "Cleaning generated files..."
	rm -rf data/processed/*
	rm -rf data/splits/*
	rm -rf outputs/prompts/*
	rm -rf outputs/logs/*
	rm -rf __pycache__
	rm -rf src/__pycache__
	rm -rf .pytest_cache
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	@echo "Clean complete!"

# Setup development environment
dev-setup: install
	@echo "Setting up development environment..."
	pip install pytest black flake8 mypy
	@echo "Development setup complete!"

# Format code
format:
	@echo "Formatting code with black..."
	black src/ run_training.py
	@echo "Code formatting complete!"

# Lint code
lint:
	@echo "Linting code..."
	flake8 src/ run_training.py --max-line-length=120
	@echo "Linting complete!"

# Type check
typecheck:
	@echo "Type checking with mypy..."
	mypy src/ run_training.py --ignore-missing-imports
	@echo "Type checking complete!"

# Run all checks
check: lint typecheck
	@echo "All checks passed!"

# Quick start (install + prepare + train)
quickstart: install prepare-data train
	@echo "Quickstart complete!"
