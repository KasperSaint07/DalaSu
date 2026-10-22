# ADR 0001: Use FastAPI for the backend

**Status:** Accepted (technology choice; implementation pending)  
**Date:** 2026-10-22

## Context

DalaSu needs an API for field records and planned irrigation recommendations. Its existing scientific pipeline uses Python, scikit-learn, and XGBoost. The API should reuse this logic and provide clear request/response contracts for the Flutter client. A two-person diploma team must maintain the implementation. NFR-05 sets a future response target of at most 3 seconds per field; no API benchmark exists yet.

## Alternatives considered

| Option | Benefits | Tradeoffs |
|---|---|---|
| FastAPI | Direct Python integration; type-based validation and OpenAPI generation. | Authentication, database integration, and migrations need explicit choices. |
| Django REST Framework | Python integration, serializers, authentication policies, and Django ecosystem. | A broader application framework than currently needed; preferable if admin-heavy workflows become central. |
| NestJS | Structured TypeScript backend with modules and dependency injection. | Keeping the Python models requires an additional runtime and integration boundary. |

## Decision

Use **FastAPI** for the backend, as confirmed by the project owner on 2026-10-22. Expose JSON endpoints to Flutter and keep calculation/inference modules independent of HTTP handlers. Prefer direct Python reuse over adding a separate inference service at this stage.

## Consequences

- Existing scientific code can be reused without a TypeScript rewrite. Django could also reuse it; FastAPI is selected for this API-focused scope.
- Train offline and load trusted model artifacts for inference; do not train models in a request.
- Async I/O does not remove CPU-bound inference costs. Profile the implementation and isolate expensive work as needed.
- Implement access control, error handling, database migrations, and explicit units/data-freshness fields. Generated documentation is not a security guarantee.
- Verify API contracts and measure NFR-05 on a documented environment before claiming compliance.

## Revisit when

Reconsider if an admin-centered application becomes the main scope, a TypeScript backend becomes mandatory, or measured inference/deployment constraints require a separate service.

## References

- [Technology comparison: backend and criteria](../05-technology-comparison.md#3-backend-framework).
- [FastAPI features](https://fastapi.tiangolo.com/features/).
- [FastAPI concurrency](https://fastapi.tiangolo.com/async/).
- [Django REST Framework](https://www.django-rest-framework.org/).
- [NestJS](https://docs.nestjs.com/).
