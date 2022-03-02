/*
 * SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: MIT
 */


#include "riva_asr_client_helper.h"

bool
WaitUntilReady(
    std::shared_ptr<grpc::Channel> channel, std::chrono::system_clock::time_point& deadline)
{
  auto state = channel->GetState(true);
  while (state != GRPC_CHANNEL_READY) {
    if (!channel->WaitForStateChange(state, deadline)) {
      return false;
    }
    state = channel->GetState(true);
  }
  return true;
}


bool
OpenAudioDevice(
    const char* devicename, snd_pcm_t** handle, snd_pcm_stream_t stream_type, int channels,
    int rate, unsigned int latency)
{
  int rc;
  static snd_output_t* log;

  std::cerr << "latency " << latency << std::endl;

  if ((rc = snd_pcm_open(handle, devicename, stream_type, 0)) < 0) {
    printf("unable to open pcm device for recording: %s\n", snd_strerror(rc));
    return false;
  }

  if ((rc = snd_output_stdio_attach(&log, stderr, 0)) < 0) {
    printf("unable to attach log output: %s\n", snd_strerror(rc));
    return false;
  }

  if ((rc = snd_pcm_set_params(
           *handle, SND_PCM_FORMAT_S16_LE, SND_PCM_ACCESS_RW_INTERLEAVED, channels, rate,
           1 /* resample = false */, latency)) < 0) {
    printf("snd_pcm_set_params error: %s\n", snd_strerror(rc));
    return false;
  }

  if (stream_type == SND_PCM_STREAM_CAPTURE) {
    snd_pcm_sw_params_t* sw_params = NULL;
    if ((rc = snd_pcm_sw_params_malloc(&sw_params)) < 0) {
      printf("snd_pcm_sw_params_malloc error: %s\n", snd_strerror(rc));
      return false;
    }

    if ((rc = snd_pcm_sw_params_current(*handle, sw_params)) < 0) {
      printf("snd_pcm_sw_params_current error: %s\n", snd_strerror(rc));
      return false;
    }

    if ((rc = snd_pcm_sw_params_set_start_threshold(*handle, sw_params, 1)) < 0) {
      printf("snd_pcm_sw_params_set_start_threshold failed: %s\n", snd_strerror(rc));
      return false;
    }

    if ((rc = snd_pcm_sw_params(*handle, sw_params)) < 0) {
      printf("snd_pcm_sw_params failed: %s\n", snd_strerror(rc));
      return false;
    }

    snd_pcm_sw_params_free(sw_params);
  }

  // snd_pcm_dump(*handle, log);
  snd_output_close(log);
  return true;
}

bool
CloseAudioDevice(snd_pcm_t** handle)
{
  if (*handle != NULL) {
    snd_pcm_drain(*handle);
    snd_pcm_close(*handle);
    *handle = nullptr;
  }
  return true;
}
