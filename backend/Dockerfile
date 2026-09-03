# backend/Dockerfile
#
# Runtime image for the api / worker / seed services. Installs the pinned runtime
# closure from requirements.lock (reproducible builds), then the app itself with
# --no-deps. No dev toolchain (pytest/ruff/black/mypy) ships here — CI installs
# that directly on the runner. Runs as a non-root user.
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.lock ./
RUN pip install -r requirements.lock

COPY . .
RUN pip install -e . --no-deps

# Drop privileges. The source tree is owned by root and left world-readable by
# the base image, which is enough for the app to import and run; the app never
# writes into /app.
RUN adduser --system --no-create-home --group app
USER app

# --proxy-headers + --forwarded-allow-ips=*: the api port is only reachable from
# the compose network (Caddy is the sole ingress and sets X-Forwarded-For), so
# trusting the forwarded client IP is safe — and required for the per-client-IP
# rate limiter to bucket real callers rather than the proxy's single address.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
