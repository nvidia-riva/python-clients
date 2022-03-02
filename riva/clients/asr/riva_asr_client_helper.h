/*
 * SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: MIT
 */

#pragma once

#include <alsa/asoundlib.h>
#include <grpcpp/grpcpp.h>

#include <iostream>
#include <sstream>

#include "absl/strings/str_replace.h"

bool WaitUntilReady(
    std::shared_ptr<grpc::Channel> channel, std::chrono::system_clock::time_point& deadline);

bool OpenAudioDevice(
    const char* devicename, snd_pcm_t** handle, snd_pcm_stream_t stream_type, int channels,
    int rate, unsigned int latency);

bool CloseAudioDevice(snd_pcm_t** handle);

std::string static inline EscapeTranscript(const std::string& input_str)
{
  return absl::StrReplaceAll(input_str, {{"\"", "\\\""}});
}
