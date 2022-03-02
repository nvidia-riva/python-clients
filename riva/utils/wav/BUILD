"""
Copyright (c) 2021, NVIDIA CORPORATION.  All rights reserved.
NVIDIA CORPORATION and its licensors retain all intellectual property
and proprietary rights in and to this software, related documentation
and any modifications thereto.  Any use, reproduction, disclosure or
distribution of this software and related documentation without an express
license agreement from NVIDIA CORPORATION is strictly prohibited.
"""

package(
    default_visibility = ["//visibility:public"],
)

cc_library(
    name = "writer",
    srcs = ["wav_writer.cc"],
    hdrs = ["wav_writer.h"]
)

cc_library(
    name = "reader",
    srcs = ["wav_reader.cc"],
    hdrs = ["wav_reader.h", "wav_data.h"],
    deps = [
        "//riva/proto:riva_grpc_asr",
        "@rapidjson//:rapidjson",
        "@glog//:glog",
    ]
)