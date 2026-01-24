# Contributing to KomanSim

Thank you for your interest in contributing to KomanSim! This document provides guidelines and instructions for contributing.

## Development Setup

### Prerequisites
- Python 3.10 or 3.11
- Git

### Setup Steps

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd KomanSim
   ```

2. **Create a virtual environment**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\Activate.ps1
   ```

3. **Install in development mode**
   ```bash
   pip install -e ".[dev]"
   ```

4. **Verify installation**
   ```bash
   komansim --help
   pytest -q
   ```

## Running Tests

```bash
# Run all tests
pytest tests/

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/test_sdk_smoke.py

# Run with coverage
pytest --cov=komansim tests/
```

## Code Style

We use [ruff](https://github.com/astral-sh/ruff) for linting and formatting.

```bash
# Check code style
ruff check komansim/

# Auto-fix issues
ruff check --fix simdata/

# Format code (if configured)
ruff format komansim/
```

### Style Guidelines
- Line length: 100 characters
- Use type hints for function signatures
- Follow PEP 8 conventions
- Use descriptive variable and function names

## Making Changes

1. **Create a branch**
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/your-bug-fix
   ```

2. **Make your changes**
   - Write clear, focused commits
   - Add tests for new features
   - Update documentation as needed

3. **Run tests and linting**
   ```bash
   pytest -q
   ruff check komansim/
   ```

4. **Commit your changes**
   ```bash
   git add .
   git commit -m "Description of your changes"
   ```

5. **Push and create a pull request**
   ```bash
   git push origin feature/your-feature-name
   ```

## Pull Request Process

1. **Ensure all tests pass**
   - CI will run automatically on your PR
   - Make sure local tests pass before submitting

2. **Update documentation**
   - Update README.md if adding new features
   - Update CHANGELOG.md for user-facing changes
   - Add docstrings for new functions/classes

3. **Write a clear PR description**
   - Explain what changes you made and why
   - Reference any related issues
   - Include examples if adding new features

4. **Respond to feedback**
   - Address review comments promptly
   - Make requested changes in new commits (don't force-push)

## Adding New Backends

If you're adding a new backend:

1. Create a new module in `komansim/backends/<backend_name>/`
2. Implement the `SimBackend` interface (see `komansim/core/backend.py`)
3. Register the backend in `komansim/core/registry.py`
4. Add tests in `tests/test_backends/`
5. Update documentation in README.md

## Adding New Exporters

If you're adding a new export format:

1. Create a new exporter in `komansim/pipeline/exporters/`
2. Follow the pattern of existing exporters (COCO, YOLO)
3. Add tests
4. Update documentation

## Reporting Bugs

If you find a bug:

1. Check if it's already reported in the issues
2. Create a new issue with:
   - Clear description of the problem
   - Steps to reproduce
   - Expected vs. actual behavior
   - Environment details (Python version, OS, etc.)
   - Minimal example if possible

## Asking Questions

For questions or discussions:
- Open a GitHub Discussion
- Check existing issues and discussions first

## Code of Conduct

Please note that this project follows a Code of Conduct. By participating, you are expected to uphold this code.

## License

By contributing, you agree that your contributions will be licensed under the Apache-2.0 license.
