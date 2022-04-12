"""
SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
SPDX-License-Identifier: MIT
"""

package(default_visibility = ["//visibility:public"])

load("@com_github_grpc_grpc//bazel:cc_grpc_library.bzl", "cc_grpc_library")

cc_grpc_library(
    name = "riva_audio_proto",
    srcs = [
        ":riva_audio.proto"
    ],
    deps = [],
)

cc_grpc_library(
    name = "riva_grpc_asr",
    srcs = [":riva_asr.proto"],
    deps = [":riva_audio_proto"],
)

cc_grpc_library(
    name = "riva_grpc_tts",
    srcs = [":riva_tts.proto"],
    deps = [":riva_audio_proto"]
)

cc_grpc_library(
    name = "riva_grpc_nlp",
    srcs = [":riva_nlp.proto"],
    deps = []
)

cc_grpc_library(
    name = "riva_grpc_health",
    srcs = [":health.proto"],
    deps = []
)
