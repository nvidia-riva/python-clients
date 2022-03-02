"""
SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
SPDX-License-Identifier: MIT
"""

package(
    default_visibility = ["//visibility:public"],
)

cc_library(
    name = "riva_nlp_client",
    hdrs = ["riva_nlp_client.h"],
    deps = [
        "//riva/proto:riva_grpc_nlp",
        "@com_github_gflags_gflags//:gflags",
        "@glog//:glog",
        "@com_github_grpc_grpc//:grpc++"
    ]
)

cc_binary(
    name = "riva_nlp_classify_tokens",
    srcs = ["riva_nlp_classify_tokens.cc","riva_nlp_client.h"],
    deps = [
        ":riva_nlp_client",
        "//riva/clients/utils:grpc",
        "//riva/utils:stamping",
    ]
)

cc_binary(
    name = "riva_nlp_qa",
    srcs = ["riva_nlp_qa.cc","riva_nlp_client.h"],
    deps = [
        ":riva_nlp_client",
        "//riva/clients/utils:grpc",
        "//riva/utils:stamping",
    ]
)

cc_binary(
    name = "riva_nlp_punct",
    srcs = ["riva_nlp_punct.cc","riva_nlp_client.h"],
    deps = [
        ":riva_nlp_client",
        "//riva/clients/utils:grpc",
        "//riva/utils:stamping",
    ]
)

