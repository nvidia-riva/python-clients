/*
 * SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: MIT
 */

#pragma once

#include <strings.h>
#include <unistd.h>

#include <fstream>

namespace riva::utils::files {

/// Utility function to read a file content
///
/// Retuns a string with file content
/// Throws an error if file cannot be opened

/// @param[in]: filename The file path

std::string ReadFileContentAsString(const std::string filename);

}  // namespace riva::utils::files
