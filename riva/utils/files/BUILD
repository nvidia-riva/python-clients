"""
 * SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: MIT
"""

package(
    default_visibility = ["//visibility:public"],
)

cc_library(
    name = "files",
    srcs = ["files.cc"],
    hdrs = ["files.h"]
)

cc_test(
    name = "files_test",
    srcs = ["files_test.cc",],
    deps = [
        ":files",
        "@googletest//:gtest_main",
    ],
    linkopts = ["-lm"],
    linkstatic = True,
)

