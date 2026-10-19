# postgis 16-3.4 is Debian bullseye, whose pgdg apt repo is gone (pgvector cannot be installed); 3.5 is bookworm-based.
FROM postgis/postgis:16-3.5

# Install pgvector
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       postgresql-16-pgvector \
    && rm -rf /var/lib/apt/lists/*

# Copy initialization scripts
COPY init/ /docker-entrypoint-initdb.d/
