## v0.8.10 (2026-04-26)

### Fix

- **db**: add cascade to ai_insights relationship (#64)

## v0.8.9 (2026-04-26)

### Fix

- **celery**: import resolution_tasks to celery app

## v0.8.8 (2026-04-26)

### Fix

- **storage**: fix oci object storage content length header issue

## v0.8.7 (2026-04-25)

### Fix

- **storage**: fix content length error

## v0.8.6 (2026-04-25)

### Fix

- **storage**: fix content length error

## v0.8.5 (2026-04-25)

### Fix

- **storage**: force path-style addressing for OCI S3 compatibility

## v0.8.4 (2026-04-25)

### Fix

- **storage**: wrap OCI S3 payloads in BytesIO and add module docstrings

## v0.8.3 (2026-04-25)

## v0.8.2 (2026-04-25)

### Fix

- **storage**: explicit content-length for OCI S3 compatibility

## v0.8.1 (2026-04-25)

### Feat

- **delivery**: integrate UNG email notification payload and markdown conversion (#63)

### Fix

- **Helm**: increase celery beat memory limits

## v0.8.0 (2026-04-25)

### Feat

- **delivery**: integrate UNG email notification payload and markdown conversion (#63)

## v0.7.1 (2026-04-25)

### Fix

- **ci**: Updated Celery tasks path in container command (#62)

## v0.7.0 (2026-04-25)

### Feat

- **version**: added v to version

## 0.6.1 (2026-04-25)

## 0.6.0 (2026-04-24)

### Feat

- **api**: add job status tracking endpoint for celery observability (#59)
- **api**: add manual vendor mapping fallback endpoint (#58)
- **scheduler**: route active targets with vendor mappings in daily dispatcher (#57)
- **orchestrator**: implement resolution orchestrator and state machine (#55)
- **api**: refactor targets POST endpoint to trigger resolution engine (#53)
- **db**: implement security master mapping and target lifecycle (#52)

### Fix

- **api-tests**: mock celery task in get_all_targets setup (#54)

## 0.5.0 (2026-04-11)

### Feat

- **dlq**: implement dead letter queue alerting via UNG (#50)
- **scheduler**: implement celery beat master dispatcher (#48)
- **delivery**: integrate UNG client and resolve async db pooling (AE25) (#47)
- **database**: AE34-database-orm(#46)
- **ai**: fimplement AI processing worker task (#43)
- **orchestration**: implement IngestionWorkerTask and MinIO payload storage pattern (#42)
- **orchestration**: configure Celery app and Redis broker backend (#41)
- **ingestion**: AE35 add NSE corporate announcements PDF extraction strategy (#38)

### Refactor

- **ingestion**: implement AssetContext DTO to unify vendor mappings (#40)

## 0.4.0 (2026-03-27)

### Feat

- **ai**: AE17 implement robust ContextBuilder with empty node pruning and token optimization (#34)
- **storage**: AE16 implement async MinIO S3 client for context payload storage (#32)
- **ingestion**: AE15 implement Redis-backed circuit breaker for failing sources (#30)
- **ingestion**: AE14 implement async exponential backoff and jitter decorator
- **ingestion**: AE13 implement ScreenerFetcher with BeautifulSoup parsing (#28)
- **ingestion**: AE12 implement rss strategy and add fetch_news to base interface (#22)
- **ingestion**: AE11 implement AMFI mutual fund strategy and tests (#21)
- **ingestion**: AE10 implement yfinance strategy with async wrapper and tests (#20)

### Fix

- **unit-test**: fixed import error in test_s3_client
- **coverage**: fix coverage fail issue in ci pipeline (#26)
- **coverage**: move coverage flags out of pytest ini (#25)

### Refactor

- **storage**: moved s3 client code to package called object_store (#33)
- **ingestion**: handle exceptions and raise custom exceptions (#27)
- **config**: extract hardcoded target URLs to central Pydantic settings (#23)

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
