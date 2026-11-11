FROM node:24-bookworm-slim AS web
WORKDIR /build/ui
COPY threemind-ui/package*.json ./
RUN npm ci --no-audit --no-fund
COPY threemind-ui/ ./
RUN npm run build

FROM rust:1-bookworm AS native
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /buildenv && /buildenv/bin/pip install 'maturin>=1.9,<2'
WORKDIR /build
COPY Cargo.toml Cargo.lock ./
COPY crates/ crates/
RUN /buildenv/bin/maturin build --release --locked --manifest-path crates/threemind-native/Cargo.toml --out /wheels
RUN cargo build --release --locked -p threemind-runtime

FROM python:3.12-slim-bookworm AS lab
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MPLCONFIGDIR=/tmp/matplotlib XDG_CACHE_HOME=/tmp/.cache THREEMIND_MODE=server MUJOCO_GL=osmesa
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libegl1 libegl-mesa0 libosmesa6 libglfw3 fonts-dejavu-core fonts-wqy-microhei libcairo2 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml ./
COPY deploy/constraints-linux-py312.txt deploy/constraints-linux-py312.txt
RUN apt-get update && apt-get install -y --no-install-recommends gcc pkg-config libcairo2-dev \
    && python -c "import subprocess,sys,tomllib; p=tomllib.load(open('pyproject.toml','rb'))['project']; deps=[d for d in p['dependencies'] if not d.startswith(('threemind-runtime==','threemind-transformer=='))]; subprocess.run([sys.executable,'-m','pip','install','--no-cache-dir','-c','deploy/constraints-linux-py312.txt',*deps,*p['optional-dependencies']['media']],check=True)" \
    && apt-get purge -y --auto-remove gcc pkg-config libcairo2-dev \
    && rm -rf /var/lib/apt/lists/*
COPY src/ src/
COPY packages/runtime/ packages/runtime/
COPY packages/transformer/ packages/transformer/
RUN pip install --no-cache-dir --no-deps -e packages/runtime -e packages/transformer -e .
COPY --from=native /wheels/ /wheels/
RUN pip install --no-cache-dir /wheels/*.whl && rm -rf /wheels
COPY --from=native /build/target/release/threemind-runtime /usr/local/bin/threemind-runtime-native
COPY migrations/ migrations/
COPY Cargo.toml Cargo.lock ./
COPY crates/ crates/
COPY docs/ docs/
COPY --from=web /build/ui/dist/ threemind-ui/dist/
RUN useradd --create-home --uid 10001 threemind
USER threemind
EXPOSE 8877
CMD ["python", "-m", "threemind_lab.cli", "serve", "--host", "0.0.0.0"]

FROM debian:bookworm-slim AS runtime
COPY --from=native /build/target/release/threemind-runtime /usr/local/bin/threemind-runtime
USER 65534:65534
ENTRYPOINT ["threemind-runtime"]

FROM python:3.12-slim-bookworm AS runtime-python
WORKDIR /app
COPY src/threemind_core/ src/threemind_core/
COPY src/threemind_kernels/ src/threemind_kernels/
COPY src/threemind_runtime/ src/threemind_runtime/
COPY packages/runtime/ packages/runtime/
RUN pip install --no-cache-dir packages/runtime
COPY --from=native /wheels/ /wheels/
RUN pip install --no-cache-dir /wheels/*.whl && rm -rf /wheels
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 65534:65534
ENTRYPOINT ["threemind-runtime"]
