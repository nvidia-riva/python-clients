/*
 * SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: MIT
 */


#pragma once

#include <cstddef>
#include <string>

namespace riva::utils::wav {

/**
 * @brief Write a mono sample data to a WAV file.
 *
 * @param filename The file name.
 * @param frequency The sample frequency.
 * @param data The raw data.
 * @param numSamples The number of samples.
 */
void Write(const std::string& filename, int frequency, const float* data, size_t numSamples);

}  // namespace riva::utils::wav
