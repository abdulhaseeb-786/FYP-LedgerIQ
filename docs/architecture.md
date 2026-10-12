# System Architecture Documentation

## 1. Architectural Style: Modular Monolith (Vertical Slice)

LedgerIQ is architected as a **Service-Ready Modular Monolith**. Features are organized by domain capability (Vertical Slices):
- Users & Organizations
- Projects & Workspaces
- Financial Statements

## 2. Shared vs. Isolated Boundaries
- `app/core/`: Shared infrastructure (config, database session, security, exceptions, logging, middleware).
- `app/common/`: Common helpers (pagination, standard API response wrappers).
- `app/modules/<feature>/`: Isolated domain slices.

## 3. Scaling & Evolution Path
- Phase 1 & 2: Single process FastAPI + Postgres + Redis.
- Phase 3: Horizontally scaled replicas behind Nginx.
- Future: Selective microservice extraction.
