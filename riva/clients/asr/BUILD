"""
SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
SPDX-License-Identifier: MIT
"""

package(
    default_visibility = ["//visibility:public"],
)

cc_library(
    name = "asr_client_helper",
    srcs = ["riva_asr_client_helper.h", "riva_asr_client_helper.cc"],
    deps = [
        "@alsa//:libasound",
        "@com_github_grpc_grpc//:grpc++",
        "@com_google_absl//absl/strings",
    ],
)

cc_library(
    name = "client_call",
    srcs = ["client_call.h", "client_call.cc"],
    deps = [
        "@alsa//:libasound",
        "@com_github_grpc_grpc//:grpc++",
        ":asr_client_helper",
        "//riva/proto:riva_grpc_asr",
        "//riva/utils/wav:reader",
    ],
)

cc_library(
    name = "streaming_recognize_client",
    srcs = ["streaming_recognize_client.h", 
            "streaming_recognize_client.cc"
    ],
    deps = [
        ":asr_client_helper",
        ":client_call",
        "//riva/utils/wav:reader",
        "@glog//:glog",
        "@alsa//:libasound",
        "@com_github_grpc_grpc//:grpc++",
        "@com_github_gflags_gflags//:gflags",
        "//riva/proto:riva_grpc_asr",
        "//riva/utils:thread_pool",
    ],
)

cc_binary(
    name = "riva_asr_client",
    srcs = ["riva_asr_client.cc"],
    deps = [
        ":asr_client_helper",
        ":client_call",
        "//riva/proto:riva_grpc_asr",
        "//riva/utils:stamping",
        "//riva/utils/files:files",
        "//riva/utils/wav:reader",
        "@glog//:glog",
        "@com_github_grpc_grpc//:grpc++",
        "@com_github_gflags_gflags//:gflags",
        "//riva/clients/utils:grpc",
    ]
)

cc_binary(
    name = "riva_streaming_asr_client",
    srcs = ["riva_streaming_asr_client.cc"],
    deps = [
        ":asr_client_helper",
        ":client_call",
        ":streaming_recognize_client",
        "//riva/proto:riva_grpc_asr",
        "//riva/utils:stamping",
        "//riva/utils/files:files",
        "//riva/utils/wav:reader",
        "@glog//:glog",
        "//riva/clients/utils:grpc",
        "@alsa//:libasound",
        "@com_github_grpc_grpc//:grpc++",
        "@com_github_gflags_gflags//:gflags",
    ],
)

cc_test(
    name = "streaming_recognize_client_test",
    srcs = ["streaming_recognize_client_test.cc"],
    copts = ["-Iexternal/gtest/include"],
    deps = [
        ":streaming_recognize_client",
        "@googletest//:gtest_main",
        "//riva/proto:riva_grpc_asr",
    ],
    tags = ["needs_alsa"]
)

config_setting(
    name = "cpu_arch_aarch64",
    values = {"define": "aarch64_build=1"},
)

