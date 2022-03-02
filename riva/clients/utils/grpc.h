/*
 * SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: MIT
 */

#pragma once

#include <gflags/gflags.h>
#include <glog/logging.h>
#include <grpcpp/grpcpp.h>
#include <strings.h>

#include <chrono>
#include <string>

using grpc::Status;
using grpc::StatusCode;

namespace riva::clients {

/// Utility function to create a GRPC channel
/// This will only return when the channel has been created, thus making sure that the subsequent
/// GRPC call won't have additional latency due to channel creation
///
/// @param uri URI of server
/// @param credentials GRPC credentials
/// @param timeout_ms The maximum time (in milliseconds) to wait for channel creation. Throws
/// exception if time is exceeded

std::shared_ptr<grpc::Channel>
CreateChannelBlocking(
    const std::string& uri, const std::shared_ptr<grpc::ChannelCredentials> credentials,
    uint64_t timeout_ms = 10000)
{
  auto channel = grpc::CreateChannel(uri, credentials);

  auto deadline = std::chrono::system_clock::now() + std::chrono::milliseconds(timeout_ms);
  auto reached_required_state = channel->WaitForConnected(deadline);
  auto state = channel->GetState(true);

  if (!reached_required_state) {
    DLOG(WARNING) << "Unable to establish connection to server. Current state: " << (int)state;
    throw std::runtime_error(
        "Unable to establish connection to server. Current state: " + std::to_string((int)state));
  }

  return channel;
}

}  // namespace riva::clients
