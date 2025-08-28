# Contributing to MCP Handley Lab Toolkit

Thank you for your interest in contributing! This is beta software with room for improvement, and we welcome all contributions.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone git@github.com:your-username/mcp-handley-lab.git
   cd mcp-handley-lab
   ```
3. **Set up the development environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -e ".[dev]"
   ```
4. **Create a feature branch**:
   ```bash
   git checkout -b feature/amazing-feature
   ```

## Development Guidelines

### Project Structure
- Each tool is a self-contained Python module in `src/mcp_handley_lab/`
- Shared logic goes in `src/mcp_handley_lab/common/`
- Tests are organized in `tests/` with unit and integration categories
- Follow existing patterns when adding new tools

### Code Quality
We use modern Python tooling for code quality:

```bash
# Format and lint code
ruff format .
ruff check . --fix

# Run tests with coverage
pytest --cov=mcp_handley_lab --cov-report=term-missing

# Run only unit tests (fast)
pytest -m unit

# Run integration tests (requires API keys)
pytest -m integration
```

### Version Management
**CRITICAL**: Always bump the version before making commits:

```bash
# Auto-detect minimal version bump
python scripts/bump_version.py

# Or specify bump type
python scripts/bump_version.py beta    # For development iterations
python scripts/bump_version.py patch   # For bug fixes
python scripts/bump_version.py minor   # For new features
python scripts/bump_version.py major   # For breaking changes

# Test first with dry-run
python scripts/bump_version.py --dry-run
```

The script automatically updates both `pyproject.toml` and `PKGBUILD`. **Never edit version numbers manually.**

### Adding New Tools

1. **Study existing tools** in `src/mcp_handley_lab/` to understand patterns
2. **Create your tool module** following the established structure
3. **Add entry points** in `pyproject.toml` under `[project.scripts]`
4. **Write comprehensive tests** including both unit and integration tests
5. **Update documentation** as needed

### Testing Strategy

We use a multi-layered testing approach:

- **Unit Tests**: Mock external dependencies, test business logic
- **Integration Tests**: Test real tool interactions and API calls
- **MCP Protocol Tests**: All integration tests use MCP protocol via `call_tool()`

### Pre-commit Hooks

This project uses pre-commit hooks to enforce code quality:

```bash
# Install pre-commit hooks
pre-commit install

# Run hooks manually
pre-commit run --all-files
```

**Never use `--no-verify`** to skip these checks. If hooks fail, fix the issues properly.

## Submitting Changes

1. **Test your changes**:
   ```bash
   pytest
   ruff check .
   ruff format .
   ```

2. **Commit your changes** (version should already be bumped):
   ```bash
   git add .
   git commit -m "feat: add amazing new feature"
   ```

3. **Push to your fork**:
   ```bash
   git push origin feature/amazing-feature
   ```

4. **Create a Pull Request** on GitHub

## Types of Contributions

### Bug Reports
Please include:
- Clear reproduction steps
- Expected vs actual behavior
- Environment details (Python version, OS, etc.)
- Error messages or logs

### Feature Requests
Please describe:
- Your use case and problem
- Proposed solution or API
- Why existing tools don't meet your needs

### Documentation
- Fix typos or unclear instructions
- Add examples or use cases
- Improve setup or troubleshooting guides

### Code Contributions
- Bug fixes and improvements
- New MCP tools following project patterns
- Test coverage improvements
- Performance optimizations

## Development Philosophy

This project follows these principles:

- **Concise Elegance**: Every line should justify its existence
- **Functional Design**: Prefer stateless functions over classes with mutable state
- **Minimal Abstractions**: Only introduce abstractions to remove significant duplication
- **Beta Software Mindset**: APIs may change to improve design, though we aim for stability
- **Fail Fast and Loud**: Errors should be fixed, not hidden
- **100% Test Coverage**: Gaps indicate untested logic or refactoring opportunities

## Getting Help

- **Questions about architecture**: Open a discussion or issue
- **Implementation help**: Look at existing tools as examples
- **Testing guidance**: Check `tests/` directory for patterns
- **MCP Protocol**: See [official MCP documentation](https://modelcontextprotocol.io/)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
