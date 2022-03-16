# syntax = docker/dockerfile:1.2

FROM ubuntu:20.04 AS base
ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y libasound2    

FROM base AS builddep
ARG BAZEL_VERSION=5.0.0

RUN apt-get update && apt-get install -y \
    git \
    wget \
    unzip \
    build-essential \
    libasound2-dev

RUN wget https://github.com/bazelbuild/bazel/releases/download/${BAZEL_VERSION}/bazel-${BAZEL_VERSION}-installer-linux-x86_64.sh && \
    chmod +x bazel-${BAZEL_VERSION}-installer-linux-x86_64.sh && \
    ./bazel-${BAZEL_VERSION}-installer-linux-x86_64.sh --user && \
    echo "PATH=/root/bin:$PATH\n" >> /root/.bashrc && \
    echo "source /root/.bazel/bin/bazel-complete.bash" >> /root/.bashrc && \
    rm ./bazel-${BAZEL_VERSION}-installer-linux-x86_64.sh
ENV PATH="/root/bin:${PATH}"

FROM builddep as builder

WORKDIR /work
COPY .bazelrc .gitignore WORKSPACE ./
COPY .git /work/.git
COPY scripts /work/scripts
COPY third_party /work/third_party
COPY riva /work/riva
ARG BAZEL_CACHE_ARG=""
RUN bazel test $BAZEL_CACHE_ARG //riva/clients/... --test_summary=detailed --test_output=all
RUN bazel build --stamp --config=release $BAZEL_CACHE_ARG //... && \
    cp -R /work/bazel-bin/riva /opt

RUN ls -lah /work; ls-lah /work/.git; cat /work/.bazelrc

FROM base as riva-clients

WORKDIR /work
COPY --from=builder /opt/riva/clients/asr/riva_asr_client /usr/local/bin/ 
COPY --from=builder /opt/riva/clients/asr/riva_streaming_asr_client /usr/local/bin/ 
COPY --from=builder /opt/riva/clients/tts/riva_tts_client /usr/local/bin/ 
COPY --from=builder /opt/riva/clients/tts/riva_tts_perf_client /usr/local/bin/ 
COPY --from=builder /opt/riva/clients/nlp/riva_nlp_classify_tokens /usr/local/bin/ 
COPY --from=builder /opt/riva/clients/nlp/riva_nlp_punct /usr/local/bin/ 
COPY --from=builder /opt/riva/clients/nlp/riva_nlp_qa /usr/local/bin/
COPY examples /work/examples
