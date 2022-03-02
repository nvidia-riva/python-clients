/*
 * SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: MIT
 */


#pragma once

#include <iostream>
#include <vector>

#include "riva/proto/riva_asr.pb.h"

namespace nr = nvidia::riva;
namespace nr_asr = nvidia::riva::asr;

enum WaveFormat : int16_t {
  kPCM = 0x0001,
  kALAW = 0x0006,
  kMULAW = 0x0007,
};

typedef struct __attribute__((packed)) {
  char chunk_id[4];  // should be "RIFF" in ASCII form
  int32_t chunk_size;
  char format[4];          // should be "WAVE"
  char subchunk1_id[4];    // should be "fmt "
  int32_t subchunk1_size;  // should be 16 for PCM format
  WaveFormat audioformat;  // should be 1 for PCM
  int16_t numchannels;
  int32_t samplerate;
  int32_t byterate;       // == samplerate * numchannels * bitspersample/8
  int16_t blockalign;     // == numchannels * bitspersample/8
  int16_t bitspersample;  //    8 bits = 8, 16 bits = 16, etc.
  char subchunk2ID[4];
  int32_t subchunk2size;
} FixedWAVHeader;

struct WaveData {
  std::vector<char> data;
  std::string filename;
  int sample_rate;
  int channels;
  nr::AudioEncoding encoding;
};


struct Stream {
  std::shared_ptr<WaveData> wav;
  float send_next_chunk_at;
  size_t offset;
  uint32_t corr_id;

  Stream(const std::shared_ptr<WaveData>& _wav, uint32_t _corr_id)
      : wav(_wav), offset(0), corr_id(_corr_id)
  {
    // send_next_chunk_at = gettime_monotonic();
    // if (online) {
    //  send_next_chunk_at += chunk_seconds;
    //}
  }
};
