# Contributing to AegisPass

Thank you for considering contributing!

## How to Contribute

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes with clear commit messages
4. Push to your fork and open a Pull Request

## Development Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your values
```

## Code Style

- Follow PEP 8
- Keep changes focused and minimal
- Update `.env.example` when adding new configuration

## Security

Never commit secrets, `.env`, certificates, or internal infrastructure details.
