# database/Dockerfile

FROM timescale/timescaledb-ha:pg14-latest

USER root

RUN rm -rf /var/lib/apt/lists/* \
    && apt-get clean \
    && apt-get update \
    && apt-get install -y postgresql-14-postgis-3 \
    && rm -rf /var/lib/apt/lists/*

USER postgres

COPY init/*.sql /docker-entrypoint-initdb.d/

ENV POSTGRES_USER=ddf_user
ENV POSTGRES_PASSWORD=ddf_password
ENV POSTGRES_DB=ddf_db