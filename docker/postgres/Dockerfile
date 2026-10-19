# The postgis/postgis:16-3.x images are Debian bullseye, whose pgdg apt repo has been removed, so pgvector cannot be
# installed on top of them. Start from the official bookworm image (pgdg repo preconfigured) and install both extensions.
# The schema runs CREATE EXTENSION itself (postgis, vector, pg_trgm, pgcrypto, btree_gist).
FROM postgres:16-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       postgresql-16-postgis-3 \
       postgresql-16-postgis-3-scripts \
       postgresql-16-pgvector \
    && rm -rf /var/lib/apt/lists/*

# Copy initialization scripts
COPY init/ /docker-entrypoint-initdb.d/
