FROM python:3-alpine AS base
FROM base AS builder
WORKDIR /install
RUN pip install --prefix /install --no-cache-dir sqlite3 requests urllib3

FROM base
COPY ./*.py /
COPY --from=builder /install /usr/local
RUN python /main.py -h