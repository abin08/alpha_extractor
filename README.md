## Alpha Extractor

AI-driven financial sentiment extraction pipeline.

### Coverage

- Local summary: `make coverage` (uses in-memory SQLite, prints term-missing, writes `coverage.xml`).
- HTML report: `make coverage-html` then open `htmlcov/index.html`.
- CI: GitHub Actions runs `make coverage` and uploads `coverage.xml` as an artifact.
