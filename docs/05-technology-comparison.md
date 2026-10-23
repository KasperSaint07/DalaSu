# 05. Technology Comparison

## 1. Purpose and evidence

This document compares three technology choices for the planned DalaSu application: the backend framework, the primary database, and the mobile framework. Each comparison includes the selected option and two alternatives, with benefits, limitations, and a project-specific rationale.

The project owner confirmed **FastAPI + PostgreSQL + Flutter** on 2026-10-22. This records the agreed architecture, not a completed application. The repository currently contains Python data processing, FAO-56 calculations, trained Random Forest and XGBoost models, and evaluation code. The API, database integration, and mobile client remain planned.

The assessment uses the [project proposal](01-project-proposal.md), [requirements](06-requirements.md), [README](../README.md), and official documentation listed below. Framework capabilities are documented facts; judgments about project fit and implementation effort are engineering assessments. No comparative latency, cost, or development-time benchmark was performed. There are no numerical rankings implying measured superiority.

## 2. Decision criteria

| Criterion | Relevance to DalaSu |
|---|---|
| Python integration | Reuse existing FAO-56 and ML code without duplicating scientific logic (FR-01–FR-04). |
| Durable, consistent storage | Preserve field, crop, and planting information (FR-09); support a future irrigation diary (FR-10). |
| Mobile delivery | Provide a practical client for farmers; retain a path to Android and iOS from shared code. |
| Maintainability | Keep the application manageable for the two-person diploma team. No unverified expertise in a framework is assumed. |
| API clarity and response time | Define validated inputs and outputs; evaluate the one-field response target of at most 3 seconds (NFR-05). |
| Future features | Allow field geometry, seasonal charts, and Kazakh/Russian UI without claiming these features already exist (FR-12–FR-13). |

The requirements include earlier wording about ET0 and hybrid models. Current ML-only models predict observed actual ET, as explained in the README and [ADR 0004](adr/0004-compare-et0-with-observed-et.md). This technology comparison does not revise those scientific requirements or claim that hybrid models have been implemented.

## 3. Backend framework

**Candidates:** FastAPI, Django REST Framework, NestJS.

| Criterion | FastAPI | Django REST Framework | NestJS |
|---|---|---|---|
| Language and scientific integration | Python; can import existing calculation and inference modules. | Python; can reuse the same modules. | Node.js/TypeScript; retaining Python models requires an integration boundary. |
| API development | Type-based validation and generated OpenAPI documentation [S1]. | Serializers, authentication policies, and a browsable API [S3]. | Modules, controllers, and dependency injection [S4]. |
| Application infrastructure | Database access, migrations, and authentication must be selected and integrated. | Fits Django's broader application ecosystem; attractive when administration and CRUD dominate. | Structured service architecture; introduces a second backend runtime if inference stays in Python. |
| DalaSu tradeoff | Direct fit for an API around existing Python logic. | Viable alternative, but the present scope does not establish a need for a Django-centered application. | Viable with a Python inference service, adding deployment and interface work for this scope. |

**Decision:** Select **FastAPI**. Direct reuse of existing Python modules and explicit API contracts outweigh the benefit of a broader application framework at this stage. Django REST Framework could also serve Python models; this is a scope choice, not a claim that it cannot support ML. NestJS remains reasonable if a TypeScript backend later becomes a firm requirement.

**Consequences:** Keep HTTP handlers separate from scientific modules. Train models outside requests and load trusted artifacts for inference. Async I/O does not make CPU-heavy computation non-blocking [S2]; profile inference and use appropriate execution isolation if needed. Authentication, authorization, database migrations, and error handling require implementation. NFR-05 remains an unverified acceptance target.

**Record:** [ADR 0001](adr/0001-use-fastapi-for-backend.md).

## 4. Primary database

**Candidates:** PostgreSQL, MySQL, MongoDB.

| Criterion | PostgreSQL | MySQL | MongoDB |
|---|---|---|---|
| Data organization | Relational tables with primary keys, foreign keys, and checks [S5]. | Relational alternative suitable for structured application records. | Document-oriented alternative; requires deliberate embedding or referencing choices. |
| Proposed domain fit | Explicit relations between fields, crop seasons, recommendations, and irrigation events. | Can represent the same relational domain; not rejected for lacking SQL capabilities. | Useful for flexible documents, but less aligned with the relational design proposed here. |
| Spatial path | Optional PostGIS extension for spatial data and operations [S6]. | Supports spatial data types [S7]. | Supports GeoJSON and geospatial queries [S8]. |
| Operational tradeoff | Requires a running database, migrations, backups, and restoration checks. | Also requires operational administration. | Also requires schema discipline and operational administration. |

**Decision:** Select **PostgreSQL** as the primary application database. Its relational constraints fit the proposed domain, while the PostGIS ecosystem provides a future path for field geometry. Spatial support is not unique to PostgreSQL and is not the sole reason for selection.

**Consequences:** Start with field coordinates and structured records. Treat **PostGIS as an optional extension**, to be evaluated when polygon storage or spatial queries are implemented; it is not an additional confirmed deployment requirement. Keep training CSVs and model artifacts in the existing reproducible pipeline rather than importing them into the application database without a use case. Schema migrations and backup procedures remain implementation work.

**Record:** [ADR 0002](adr/0002-use-postgresql-for-storage.md).

## 5. Mobile application framework

**Candidates:** Flutter, React Native, separate native Android and iOS applications.

| Criterion | Flutter | React Native | Separate native applications |
|---|---|---|---|
| Development approach | Dart and shared application code across supported platforms [S9]. | React with JavaScript/TypeScript and native components [S12]. | Kotlin/Jetpack Compose for Android and Swift/SwiftUI for iOS [S13–S14]. |
| UI and localization | Shared widget implementation; documented localization workflow [S10]. | Shared React application; localization and platform differences require implementation choices. | Platform-specific UI and localization work in each application. |
| Integration | REST/JSON client; mapping, notifications, and local persistence require suitable packages and testing. | REST/JSON client; platform integrations also require libraries and testing. | Direct platform integration with separate implementation effort. |
| DalaSu tradeoff | Matches the confirmed direction and keeps UI work in one main codebase. | Credible alternative, especially if React skills become a deciding factor; no such advantage is assumed here. | Maximum platform-specific control, but two UI implementations increase the maintenance scope. |

**Decision:** Select **Flutter**. A shared client is appropriate for the two-person project and the confirmed mobile direction. This does not imply that Flutter is universally faster or cheaper than React Native. Initial platform delivery and supported OS versions will be set during implementation; selecting Flutter does not commit to simultaneous store releases.

**Consequences:** Dart and platform build tooling are required. Verify mapping/chart packages and test on each supported platform. Kazakh and Russian remain planned features, not delivered translations. Cached screens and synchronization can be designed using an offline-first pattern [S11], but the current requirements do not mandate full offline operation. Cached recommendations must show their age; framework choice alone does not provide fresh weather or offline ML inference.

**Record:** [ADR 0003](adr/0003-use-flutter-for-mobile.md).

## 6. Integration and verification plan

The planned Flutter client calls the FastAPI API over HTTPS using JSON. The backend validates requests, accesses PostgreSQL records, and invokes the existing Python calculation/inference modules. Training remains a separate reproducible process. Weather and satellite retrieval must expose data freshness and failures explicitly.

These checks are future implementation acceptance checks, not results of this document:

| Area | Verification |
|---|---|
| Backend | Validate request/response contracts; reject invalid field inputs; verify model loading; measure one-field recommendation latency against NFR-05 on a documented environment. |
| Database | Save and restore a field after restart (FR-09); check relations and migrations; test backup restoration before relying on persisted data. |
| Mobile | Exercise field entry and recommendation display against the API on each supported platform; verify layouts and error states. Test Kazakh/Russian coverage if FR-13 is implemented. |
| Optional features | Verify stale-cache labels and synchronization if caching is added; verify geometry and area units if PostGIS is adopted. |

Revisit these decisions if an implemented prototype reveals an unsupported platform dependency, unacceptable measured latency, excessive maintenance work, or changed requirements. ML model selection is a separate empirical decision; choosing an API framework does not choose the best predictive model.

## 7. Decision index

| ADR | Decision | Status |
|---|---|---|
| [0001](adr/0001-use-fastapi-for-backend.md) | FastAPI backend | Accepted; implementation pending |
| [0002](adr/0002-use-postgresql-for-storage.md) | PostgreSQL primary storage | Accepted; implementation pending |
| [0003](adr/0003-use-flutter-for-mobile.md) | Flutter mobile client | Accepted; implementation pending |

[ADR 0004](adr/0004-compare-et0-with-observed-et.md) remains the existing scientific comparison decision and is outside these three technology choices.

## 8. Sources

Official documentation consulted on 2026-10-22. Feature descriptions are summarized; project-fit judgments are the authors' assessment.

- **S1:** [FastAPI features](https://fastapi.tiangolo.com/features/).
- **S2:** [FastAPI concurrency and async/await](https://fastapi.tiangolo.com/async/).
- **S3:** [Django REST Framework](https://www.django-rest-framework.org/).
- **S4:** [NestJS documentation](https://docs.nestjs.com/).
- **S5:** [PostgreSQL constraints](https://www.postgresql.org/docs/current/ddl-constraints.html).
- **S6:** [PostGIS documentation](https://postgis.net/documentation/).
- **S7:** [MySQL spatial data types](https://dev.mysql.com/doc/refman/8.4/en/spatial-types.html).
- **S8:** [MongoDB geospatial queries](https://www.mongodb.com/docs/manual/geospatial-queries/).
- **S9:** [Flutter platform integration](https://docs.flutter.dev/platform-integration).
- **S10:** [Flutter internationalization](https://docs.flutter.dev/ui/internationalization).
- **S11:** [Flutter offline-first support](https://docs.flutter.dev/app-architecture/design-patterns/offline-first).
- **S12:** [React Native core and native components](https://reactnative.dev/docs/intro-react-native-components).
- **S13:** [Android Jetpack Compose](https://developer.android.com/compose).
- **S14:** [Apple SwiftUI](https://developer.apple.com/swiftui/).
