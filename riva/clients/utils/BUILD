"""
SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
SPDX-License-Identifier: MIT
"""

package(
    default_visibility = ["//visibility:public"],
)

cc_library(
    name = "grpc",
    hdrs = ["grpc.h"],
    linkopts = ["-lm"],
    deps = [
        "//riva/utils/files:files",
        "@com_github_gflags_gflags//:gflags",
        "@glog//:glog",
        "@com_github_grpc_grpc//:grpc++"
    ]
)

cc_test(
    name = "grpc_test",
    srcs = ["grpc_test.cc"],
    linkopts = ["-lm"],
    deps = [
        ":grpc",
        "@googletest//:gtest_main",
    ],
    linkstatic=True
)


