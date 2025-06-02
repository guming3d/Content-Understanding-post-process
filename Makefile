.PHONY: test test-unit test-integration test-frontend test-coverage clean install-test

# Install test dependencies
install-test:
	pip install -r requirements-test.txt

# Run all tests
test:
	python -m pytest tests/ -v

# Run only unit tests
test-unit:
	python -m pytest tests/test_transcribe_videos.py tests/test_content_understanding_client.py tests/test_app.py -v

# Run integration tests
test-integration:
	python -m pytest tests/test_integration.py -v -m integration

# Run frontend tests (requires Chrome/Chromium)
test-frontend:
	python -m pytest tests/test_frontend.py -v -m frontend

# Run tests with coverage report
test-coverage:
	python -m pytest tests/ --cov=. --cov-report=html --cov-report=term-missing

# Clean test artifacts
clean:
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Run specific test file
test-file:
	@read -p "Enter test file name (e.g., test_app.py): " file; \
	python -m pytest tests/$$file -v

# Run tests in parallel (requires pytest-xdist)
test-parallel:
	python -m pytest tests/ -v -n auto

# Run tests with different Python versions (requires tox)
test-tox:
	tox
