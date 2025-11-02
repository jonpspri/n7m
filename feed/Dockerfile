FROM python:3.13-slim-bookworm

ENV NOMINATIM_VERSION=5.2.0

# https://nominatim.org/release-docs/latest/admin/Install-on-Ubuntu-24/

# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    g++ \
    libicu-dev \
    osm2pgsql>=1.8 \
    pkg-config \
    postgresql-client-15 \
 && pip install --no-cache-dir \
    nominatim_db==$NOMINATIM_VERSION \
 && apt-get purge -y --auto-remove \
    g++ \
    pkg-config \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# For settings, see: https://nominatim.org/release-docs/develop/customize/Settings/
ENV PGHOST=gis \
    PGUSER=postgres \
    PGPASSWORD=change-this-password \
    OSM_FILENAME=

RUN useradd -ms /bin/bash -d /nominatim nominatim
USER nominatim
WORKDIR /nominatim

# copy shell scripts
COPY --chmod=0755 *.sh ./

ENTRYPOINT [ "./entrypoint.sh" ]
CMD [ "setup" ]
