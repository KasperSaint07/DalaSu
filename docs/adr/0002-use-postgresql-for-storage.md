# ADR 0002: Use PostgreSQL for primary application storage

**Status:** Accepted (technology choice; implementation pending)  
**Date:** 2026-10-22

## Context

FR-09 requires field, crop, and planting-date records to survive application restarts. Planned recommendations and an optional irrigation diary introduce related records. DalaSu therefore needs durable application storage with explicit data integrity rules. Field geometry may become relevant later; it is not necessary to move scientific training CSVs or model artifacts into this database.

## Alternatives considered

| Option | Benefits | Tradeoffs |
|---|---|---|
| PostgreSQL | Relational constraints; optional PostGIS path for future spatial queries. | Requires database administration, migrations, and backups. |
| MySQL | Relational storage and spatial data types; can support the core domain. | Also requires administration; no project-specific advantage over the confirmed PostgreSQL direction is established. |
| MongoDB | Flexible documents, GeoJSON storage, and geospatial queries. | Requires embedding/referencing decisions; less aligned with the proposed relational domain. |

## Decision

Use **PostgreSQL** as the primary application database, as confirmed by the project owner on 2026-10-22. Model field ownership and related seasonal/application records using explicit relations and constraints. The exact schema remains implementation work.

Treat **PostGIS as an optional extension**, to be evaluated when field polygons or spatial queries are implemented. It is not a separately confirmed requirement. MySQL and MongoDB also support spatial use cases; spatial support alone does not justify this choice.

## Consequences

- Persist structured application records with identifiers, relations, and suitable validity checks.
- Keep processed training CSVs and model artifacts in the existing scientific pipeline unless a concrete application use case requires database storage.
- Implement migrations, authorized access, backup procedures, and restoration checks.
- If polygon support is introduced, define coordinate reference systems and area units, and verify geometry handling before adopting PostGIS in deployment.
- Verify FR-09 by saving and reading a field after restart. Database selection alone does not prove persistence or data correctness.

## Revisit when

Reconsider if actual data access becomes predominantly document-oriented, deployment constraints prevent operating PostgreSQL, or measured spatial requirements change the storage design.

## References

- [Technology comparison: database](../05-technology-comparison.md#4-primary-database).
- [PostgreSQL constraints](https://www.postgresql.org/docs/current/ddl-constraints.html).
- [PostGIS documentation](https://postgis.net/documentation/).
- [MySQL spatial data types](https://dev.mysql.com/doc/refman/8.4/en/spatial-types.html).
- [MongoDB geospatial queries](https://www.mongodb.com/docs/manual/geospatial-queries/).
