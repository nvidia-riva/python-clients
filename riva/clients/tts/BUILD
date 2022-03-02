"""
SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
SPDX-License-Identifier: MIT
"""

package(
    default_visibility = ["//visibility:public"],
)

cc_binary(
    name = "riva_tts_client",
    srcs = ["riva_tts_client.cc"],
    deps = [
        "//riva/proto:riva_grpc_tts",
        "//riva/utils:stamping",
        "//riva/utils/wav:writer",
        "@glog//:glog",
        "@com_google_absl//absl/time",
        "@com_github_gflags_gflags//:gflags",
        "@com_github_grpc_grpc//:grpc++",
        "//riva/clients/utils:grpc",
    ]
)

cc_binary(
    name = "riva_tts_perf_client",
    srcs = ["riva_tts_perf_client.cc"],
    deps = [
        "//riva/proto:riva_grpc_tts",
        "//riva/utils:stamping",
        "//riva/utils/wav:writer",
        "@glog//:glog",
        "@com_github_gflags_gflags//:gflags",
        "@com_github_grpc_grpc//:grpc++",
        "//riva/clients/utils:grpc",
    ]
)
