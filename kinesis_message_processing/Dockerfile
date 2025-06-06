# Base image with cargo-chef and cargo-lambda
FROM ghcr.io/cargo-lambda/cargo-lambda:latest AS chef
WORKDIR /usr/src/app
RUN cargo install cargo-chef

# Planner stage - generates recipe.json
FROM chef AS planner
COPY Cargo.toml Cargo.lock ./
COPY lambda/ ./lambda/
COPY test/ ./test/
RUN cargo chef prepare --recipe-path recipe.json

# Cacher stage - builds dependencies
FROM chef AS cacher
COPY --from=planner /usr/src/app/recipe.json recipe.json
RUN cargo chef cook --release --recipe-path recipe.json

# Builder stage - builds the app
FROM chef AS builder
WORKDIR /usr/src/app
# 1. Copy dependencies first
COPY --from=cacher /usr/src/app/target target
# 2. Copy project files (Cargo.toml, source code)
COPY Cargo.toml Cargo.lock ./
COPY lambda/ ./lambda/
COPY test/ ./test/
# 3. Build the app (uses cached dependencies)
ENV PACKAGE=kinesis-lambda
ENV TARGETPLATFORM=linux/arm64
RUN case ${TARGETPLATFORM} in \
    "linux/amd64") RUST_ARCH=x86_64-unknown-linux-gnu ;; \
    "linux/arm64") RUST_ARCH=aarch64-unknown-linux-gnu ;; \
    *) exit 1 ;; \
    esac \
    && cargo lambda build --release --target ${RUST_ARCH} -p ${PACKAGE}

# Runtime stage
FROM public.ecr.aws/lambda/provided:al2023
ENV PACKAGE=kinesis-lambda
COPY --from=builder /usr/src/app/target/lambda/${PACKAGE}/bootstrap ${LAMBDA_RUNTIME_DIR}/bootstrap
RUN chmod +x ${LAMBDA_RUNTIME_DIR}/bootstrap
CMD [ "bootstrap" ]