# xnatio Docker image for scheduled XNAT admin tasks
#
# Build:
#   docker build -t xnatio:latest .
#
# Run (dry-run):
#   docker run --rm \
#     -e XNAT_SERVER=https://xnat.example.org \
#     -e XNAT_USERNAME=admin \
#     -e XNAT_PASSWORD=secret \
#     -v /path/to/config:/config:ro \
#     xnatio:latest apply-label-fixes /config/patterns.json -v
#
# Run (execute):
#   docker run --rm \
#     -e XNAT_SERVER=... \
#     -v /path/to/config:/config:ro \
#     xnatio:latest apply-label-fixes /config/patterns.json --execute -v

FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy source code
COPY pyproject.toml README.md ./
COPY xnatio/ ./xnatio/

# Install package
RUN pip install --no-cache-dir .

# -------------------------------------------------------------------
FROM python:3.11-slim AS runtime

LABEL maintainer="Ricky Wong <rickywonglt15@outlook.com>"
LABEL description="xnatio CLI for XNAT admin tasks"
LABEL version="0.1.0"

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash xnatio

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin/xnatio /usr/local/bin/xnatio
COPY --from=builder /usr/local/bin/xio /usr/local/bin/xio

# Create config directory
RUN mkdir -p /config && chown xnatio:xnatio /config

# Switch to non-root user
USER xnatio

# Environment variables (to be overridden at runtime)
ENV XNAT_SERVER=""
ENV XNAT_USERNAME=""
ENV XNAT_PASSWORD=""
ENV XNAT_VERIFY_TLS="true"

# Default entrypoint is the CLI
ENTRYPOINT ["xio"]

# Default command shows help
CMD ["--help"]
