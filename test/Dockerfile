# Build stage
FROM ghcr.io/cargo-lambda/cargo-lambda:latest AS builder
ARG package
ARG TARGETPLATFORM
# Set the working directory
WORKDIR /usr/src/app

# Copy the entire project
COPY . .

# Build the Lambda function
RUN case ${TARGETPLATFORM} in \
  "linux/amd64") RUST_ARCH=x86_64-unknown-linux-gnu ;; \
  "linux/arm64") RUST_ARCH=aarch64-unknown-linux-gnu ;; \
  *) exit 1 ;; \
  esac \
  && cargo lambda build --release --target ${RUST_ARCH} --bin $package

# Runtime stage
FROM public.ecr.aws/lambda/provided:al2023

# Copy only the compiled binary
COPY --from=builder /usr/src/app/target/lambda/test/bootstrap ${LAMBDA_RUNTIME_DIR}/bootstrap

# Set executable permissions
RUN chmod +x ${LAMBDA_RUNTIME_DIR}/bootstrap

# Set the CMD to the handler
CMD [ "bootstrap" ]
