/*
 * SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: MIT
 */


#pragma once

#include <iostream>
#include <sstream>

#include "wav_data.h"

void LoadWavData(std::vector<std::shared_ptr<WaveData>>& all_wav, std::string& path);
int ParseWavHeader(std::stringstream& wavfile, FixedWAVHeader& header, bool read_header);
std::string AudioToString(nr::AudioEncoding& encoding);
