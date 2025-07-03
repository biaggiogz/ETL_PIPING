FROM ghcr.io/cargo-lambda/cargo-lambda:latest AS chef
WORKDIR /usr/src/app
RUN cargo install cargo-chef --locked


FROM chef AS planner
COPY Cargo.toml Cargo.lock ./
COPY lambda/mesagges/Cargo.toml ./lambda/mesagges/
COPY lambda/shared/Cargo.toml ./lambda/shared/
COPY lambda/websocket/Cargo.toml ./lambda/websocket/
COPY test/Cargo.toml ./test/
# Create dummy source files to satisfy cargo-chef dependency analysis
RUN mkdir -p lambda/mesagges/src lambda/shared/src lambda/websocket/src test/src && \
    touch lambda/mesagges/src/main.rs lambda/shared/src/lib.rs lambda/websocket/src/main.rs test/src/main.rs && \
    cargo chef prepare --recipe-path recipe.json


FROM chef AS cacher
COPY --from=planner /usr/src/app/recipe.json recipe.json
# Network optimizations for faster dependency resolution
ENV CARGO_NET_GIT_FETCH_WITH_CLI=true
ENV CARGO_REGISTRIES_CRATES_IO_PROTOCOL=sparse
# Cook dependencies - this is the time-consuming step that gets cached
RUN cargo chef cook --release --recipe-path recipe.json


FROM chef AS builder
WORKDIR /usr/src/app
ENV PACKAGE=kinesis-lambda
ENV TARGETPLATFORM=linux/arm64
ENV CARGO_NET_GIT_FETCH_WITH_CLI=true
ENV CARGO_REGISTRIES_CRATES_IO_PROTOCOL=sparse

# Copy pre-compiled dependencies from cacher stage
# This is the magic - dependencies are already built!
COPY --from=cacher /usr/src/app/target target

# Copy source files (this triggers rebuild only when source changes)
COPY Cargo.toml Cargo.lock ./
COPY lambda/ ./lambda/
COPY test/ ./test/


RUN case ${TARGETPLATFORM} in \
    "linux/amd64") RUST_ARCH=x86_64-unknown-linux-gnu ;; \
    "linux/arm64") RUST_ARCH=aarch64-unknown-linux-gnu ;; \
    *) exit 1 ;; \
    esac && \
    cargo lambda build --release --target ${RUST_ARCH} -p ${PACKAGE}


FROM public.ecr.aws/lambda/provided:al2023
ENV PACKAGE=kinesis-lambda
# Copy only the compiled bootstrap binary - no source code or build tools
COPY --from=builder /usr/src/app/target/lambda/${PACKAGE}/bootstrap ${LAMBDA_RUNTIME_DIR}/bootstrap
RUN chmod +x ${LAMBDA_RUNTIME_DIR}/bootstrap
CMD [ "bootstrap" ]
