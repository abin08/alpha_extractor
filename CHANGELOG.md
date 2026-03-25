## 0.3.0 (2026-03-25)

### Feat

- **ingestion**: AE09 define DataFetcher base class and FetcherFactory registry (#19)
- **helm**: AE30 Helm Chart for API and Celery Workers (#17)

### Fix

- **worker**: AE31 add missing worker module and update image pull policy (#18)
- **db**: AE29 make async engine resilient to sqlite test urls (#16)
- **github**: AE29 inject dummy DATABASE_URL into make test to satisfy pydantic in ci (#15)
- **github**: AE29 wrap lint commands with uv run for ci execution (#13)
- **github**: AE29 update make install to use uv sync for automatic venv creation (#12)

## 0.2.0 (2026-03-24)

### Feat

- **domain**: AE08 define strict pydantic schemas for gemini json output contract (#8)
- **api**: AE07 create target crud routes and register router (#7)
- **api**: AE06 build base fastapi app, cors, and di container (#6)
- **db**: AE05 define core ORM models and generate initial migration (#5)
- **db**: AE04 configure async sqlalchemy session and initialize alembic (#4)
- **core**: AE03 implement structured JSON logger and custom exception hierarchy (#3)
