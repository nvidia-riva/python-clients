/*
 * SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: MIT
 */

#include "grpc.h"

#include <string>

#include "gtest/gtest.h"

using grpc::Status;
using grpc::StatusCode;


TEST(ClientUtils, CreateChannel)
{
  try {
    auto grpc_channel = riva::clients::CreateChannelBlocking(
        "localhost:1", grpc::InsecureChannelCredentials(), 10000);
    FAIL() << "Channel creation should throw an error for invalid uri";
  }
  catch (const std::exception& e) {
    EXPECT_EQ(
        std::string(e.what()).find("Unable to establish connection") != std::string::npos, true);
  }
}
