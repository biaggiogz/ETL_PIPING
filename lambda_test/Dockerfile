#STRUCTURE FOLDER PROJECT
#├── lambda_test
#│   ├── Cargo.lock
#│   ├── Cargo.toml
#│   ├── Dockerfile
#│   ├── DockerfileDev
#│   ├── README.md
#│   ├── commandsDocker.txt
#│   ├── dummy.rs
#│   ├── event.json
#│   └── src
#│       ├── event_handler.rs
#│       └── main.rs

# Build stage
FROM ghcr.io/cargo-lambda/cargo-lambda:latest AS builder
ARG package=lambda_test
ENV PACKAGE=${package}
ARG targetplatform=linux/amd64
ENV TARGETPLATFORM=${targetplatform}
WORKDIR /usr/src/app

# Copy only Cargo.toml and Cargo.lock first
COPY Cargo.toml Cargo.lock ./

# Create a dummy source file to build dependencies
RUN mkdir -p src && \
    echo "fn main() {println!(\"dummy\");}" > src/main.rs

# Build dependencies only with caching
RUN --mount=type=cache,target=/usr/local/cargo/registry \
    --mount=type=cache,target=/usr/src/app/target \
    --mount=type=cache,target=/usr/local/cargo/git \
    case ${TARGETPLATFORM} in \
    "linux/amd64") RUST_ARCH=x86_64-unknown-linux-gnu ;; \
    "linux/arm64") RUST_ARCH=aarch64-unknown-linux-gnu ;; \
    *) exit 1 ;; \
    esac && \
    cargo lambda build --release --target ${RUST_ARCH} --bin $PACKAGE

# Remove the dummy source
RUN rm -f src/main.rs

# Copy the actual source code
COPY src/ src/

# Final build with cached dependencies
RUN --mount=type=cache,target=/usr/local/cargo/registry \
    --mount=type=cache,target=/usr/src/app/target \
    --mount=type=cache,target=/usr/local/cargo/git \
    case ${TARGETPLATFORM} in \
    "linux/amd64") RUST_ARCH=x86_64-unknown-linux-gnu ;; \
    "linux/arm64") RUST_ARCH=aarch64-unknown-linux-gnu ;; \
    *) exit 1 ;; \
    esac && \
    echo "Building for target $RUST_ARCH, package $PACKAGE" && \
    cargo lambda build --release --target ${RUST_ARCH} --bin $PACKAGE --output-dir target/lambda/${PACKAGE} && \
    echo "Build completed" && \
    ls -la target/lambda && \
    ls -la target/lambda/${PACKAGE}


RUN ls -la target/lambda/${PACKAGE}

# Runtime stage
FROM public.ecr.aws/lambda/provided:al2023
ARG package
ENV PACKAGE=${package}
COPY --from=builder /usr/src/app/target/lambda/${PACKAGE}/bootstrap ${LAMBDA_RUNTIME_DIR}/bootstrap
RUN chmod +x ${LAMBDA_RUNTIME_DIR}/bootstrap
CMD [ "bootstrap" ]