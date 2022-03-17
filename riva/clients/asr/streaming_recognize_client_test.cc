/*
 * SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: MIT
 */

#include "streaming_recognize_client.h"

#include "gtest/gtest.h"

using grpc::Status;
using grpc::StatusCode;
namespace nr = nvidia::riva;
namespace nr_asr = nvidia::riva::asr;


TEST(StreamingRecognizeClient, num_responses_requests)
{
  auto grpc_channel = grpc::CreateChannel("localhost:1", grpc::InsecureChannelCredentials());
  auto current_time = std::chrono::steady_clock::now();

  StreamingRecognizeClient recognize_client(
      grpc_channel, 1, "en-US", 1, false, false, false, false, 800, false, "dummy.txt", "dummy",
      true, true, "", 10.);

  std::shared_ptr<ClientCall> call = std::make_shared<ClientCall>(1, true);
  uint32_t num_sends = 10;
  for (uint32_t send_cnt = 0; send_cnt < num_sends; send_cnt++) {
    call->recv_times.push_back(current_time);
    call->send_times.push_back(current_time);
  }

  recognize_client.PostProcessResults(call, false);
  // Expect success;
  EXPECT_EQ(recognize_client.PrintStats(), 0);

  // Now add extract send time without receive, PrintStats should return 1
  call->send_times.push_back(current_time);
  recognize_client.PostProcessResults(call, false);

  EXPECT_EQ(recognize_client.PrintStats(), 1);
}
