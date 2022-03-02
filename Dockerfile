# syntax = docker/dockerfile:1.2

FROM ubuntu:20.04 AS base
ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y libasound2    

FROM base AS builddep
ARG BAZEL_VERSION=5.0.0

RUN apt-get update && apt-get install -y \
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
COPY .bazelrc WORKSPACE ./
COPY ./third_party/ /work/third_party
COPY ./riva /work/riva
ARG BAZEL_CACHE_ARG=""
RUN --mount=type=cache,sharing=locked,target=/root/.cache/bazel bazel build $BAZEL_CACHE_ARG \
        //riva/clients/asr:riva_asr_client \
        //riva/clients/asr:riva_streaming_asr_client \
        //riva/clients/tts:riva_tts_client \
        //riva/clients/tts:riva_tts_perf_client \
        //riva/clients/nlp:riva_nlp_classify_tokens \
        //riva/clients/nlp:riva_nlp_qa \
        //riva/clients/nlp:riva_nlp_punct \
        //riva/clients/asr/... && \
    bazel test $BAZEL_CACHE_ARG //riva/clients/... --test_summary=detailed --test_output=all && \
    cp -R /work/bazel-bin/riva /opt

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
