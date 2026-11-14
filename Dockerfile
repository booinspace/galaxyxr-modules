FROM docker.io/library/node:22-bookworm-slim AS node
FROM docker.io/library/ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 \
    PATH=/opt/venv/bin:${PATH} \
    PYTHONDONTWRITEBYTECODE=1 \
    GXR_SDK=/opt/android-sdk \
    GXR_ANDROID_JAR=/opt/android-sdk/platforms/android-37.0/android.jar \
    GXR_R8=/opt/android-sdk/cmdline-tools/latest/lib/r8.jar \
    GXR_ECJ=/opt/tools/ecj-3.39.0.jar \
    GXR_NDK28=/opt/android-sdk/ndk/28.2.13676358 \
    GXR_NDK29=/opt/android-sdk/ndk/29.0.14206865 \
    ANDROID_HOME=/opt/android-sdk \
    ANDROID_NDK_HOME=/opt/android-sdk/ndk/29.0.14206865 \
    GXR_CACHE=/work/cache \
    GXR_OUTPUT=/work/output

COPY --from=node /usr/local/bin/node /usr/local/bin/node
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential ca-certificates cmake curl git ninja-build \
    openjdk-21-jdk-headless patch pkg-config python3 python3-venv unzip xz-utils zip \
    && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --only-binary=:all: frida==17.23.3 \
    && mkdir -p /opt/tools \
    && curl -fsSL https://repo.maven.apache.org/maven2/org/eclipse/jdt/ecj/3.39.0/ecj-3.39.0.jar \
         -o /opt/tools/ecj-3.39.0.jar \
    && echo '01f5a92ac19bb2b3bf85e295a68f2c73c264369109158b566ce9b490af982948  /opt/tools/ecj-3.39.0.jar' | sha256sum -c - \
    && /opt/venv/bin/python -c "import frida; assert frida.__version__ == '17.23.3'" \
    && node --version && javac -version

WORKDIR /repo
