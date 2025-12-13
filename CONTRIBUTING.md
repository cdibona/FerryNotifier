# Contributing to FerryTrmnl

Thank you for your interest in contributing to FerryTrmnl! This document provides guidelines and instructions for contributing to the project.

## Project Structure

```
FerryTrmnl/
├── web/                    # Web application code
│   ├── app.py              # Main Flask application
│   ├── test_app.py         # Unit tests
│   └── requirements.txt    # Python dependencies
├── deployment/             # Deployment configurations
│   ├── Dockerfile          # Docker container definition
│   ├── docker-compose.yml  # Docker Compose configuration
│   ├── ferrytrmnl.service  # Systemd service file
│   ├── nginx.conf.example  # Nginx reverse proxy config
│   └── run.sh              # Quick-start development script
├── .github/
│   └── workflows/          # GitHub Actions CI/CD
│       └── deploy.yml      # Deployment workflow
├── .env.template           # Environment variables template
└── docs/                   # Documentation files
```

## Getting Started

### Prerequisites

- Python 3.8 or higher
- Git
- A WSDOT Ferries API key for testing

### Development Setup

1. Fork the repository on GitHub

2. Clone your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/FerryTrmnl.git
   cd FerryTrmnl
   ```

3. Create a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

4. Install dependencies:
   ```bash
   pip install -r web/requirements.txt
   ```

5. Set up your environment:
   ```bash
   cp .env.template .env
   # Edit .env and add your WSDOT_API_KEY
   ```

6. Create a new branch for your work:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## Making Changes

### Code Style

- Follow PEP 8 style guide for Python code
- Use meaningful variable and function names
- Add docstrings to functions and classes
- Keep functions focused and single-purpose
- Maximum line length: 100 characters (soft limit)

### Testing Your Changes

Before submitting a pull request:

1. Run the automated tests:
   ```bash
   python web/test_app.py
   ```

2. Test the application runs:
   ```bash
   python web/app.py
   ```

3. Test all endpoints:
   ```bash
   # In another terminal
   curl http://localhost:5050/health
   curl http://localhost:5050/webhook
   curl http://localhost:5050/api/ferry-status
   ```

4. Check for Python errors:
   ```bash
   python -m py_compile web/app.py
   ```

### Commit Messages

- Use clear and descriptive commit messages
- Start with a verb in present tense (e.g., "Add feature", "Fix bug")
- Keep the first line under 72 characters
- Add more details in the commit body if needed

Example:
```
Add support for multiple ferry routes

- Allow specifying route_id in query parameters
- Update documentation with route examples
- Add error handling for invalid route IDs
```

## Types of Contributions

### Bug Reports

When reporting bugs, please include:

- Clear description of the issue
- Steps to reproduce
- Expected behavior
- Actual behavior
- Your environment (OS, Python version, etc.)
- Relevant error messages or logs

### Feature Requests

When requesting features, please include:

- Clear description of the feature
- Use case and motivation
- Example of how it would work
- Any implementation ideas (optional)

### Code Contributions

We welcome contributions in these areas:

- **Bug fixes**: Fix reported issues
- **Features**: Add new functionality
- **Documentation**: Improve docs, add examples
- **Performance**: Optimize code
- **Tests**: Add test coverage
- **Refactoring**: Improve code structure

## Pull Request Process

1. **Update your fork** with the latest changes from main:
   ```bash
   git remote add upstream https://github.com/cdibona/FerryTrmnl.git
   git fetch upstream
   git rebase upstream/main
   ```

2. **Push your changes** to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```

3. **Create a Pull Request** on GitHub:
   - Go to the original repository
   - Click "New Pull Request"
   - Select your fork and branch
   - Fill in the PR template with:
     - Description of changes
     - Related issue numbers
     - Testing performed
     - Screenshots (if UI changes)

4. **Wait for CI checks**:
   - GitHub Actions will run tests automatically
   - Ensure all checks pass before requesting review

5. **Respond to feedback**:
   - Address reviewer comments
   - Push additional commits as needed
   - Keep the discussion constructive

6. **After approval**:
   - Maintainers will merge your PR
   - You can delete your feature branch

## Development Tips

### Local Testing

Use the development server for testing:
```bash
# Enable debug mode in .env
FLASK_DEBUG=True

# Run the server
python web/app.py
```

Or use the quick start script:
```bash
./deployment/run.sh
```

### Testing with Mock Data

For testing without API calls, you can modify the `fetch_ferry_status` function in `web/app.py` to return mock data during development.

### Debugging

Enable detailed logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### API Rate Limits

Be mindful of WSDOT API rate limits during development. Consider:
- Using cached responses for repeated tests
- Adding delays between API calls
- Testing with minimal API calls

### Docker Development

For testing Docker builds:
```bash
# Build from project root
docker build -f deployment/Dockerfile -t ferrytrmnl .

# Run container
docker run -p 5050:5050 --env-file .env ferrytrmnl
```

## Documentation

When adding features, please update:

- README.md - For user-facing changes
- INSTALL.md - For deployment changes
- TESTING.md - For testing-related changes
- Code comments - For complex logic
- Docstrings - For all functions

## CI/CD

This project uses GitHub Actions for continuous integration and deployment:

- **Tests**: Run on every push and pull request
- **Staging deployment**: Triggers on merge to main
- **Production deployment**: Triggers on release/tag creation

See `.github/workflows/deploy.yml` for the full configuration.

## Questions?

If you have questions about contributing:

- Open an issue with the "question" label
- Check existing issues and discussions
- Review the documentation

## Code of Conduct

- Be respectful and constructive
- Welcome newcomers
- Focus on what's best for the project
- Accept constructive criticism gracefully

## License

By contributing, you agree that your contributions will be licensed under the same license as the project (MIT License).

Thank you for contributing to FerryTrmnl!
