/*
 * SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: MIT
 */

#include "files.h"

#include <fstream>
#include <sstream>
#include <string>

namespace riva::utils::files {

std::string
ReadFileContentAsString(const std::string filename)
{
  if (access(filename.c_str(), F_OK) == -1) {
    std::string err = "File " + filename + " does not exist";
    throw std::runtime_error(err);
  } else {
    std::ifstream file(filename);
    std::stringstream buffer;
    buffer << file.rdbuf();
    return buffer.str();
  }
}

}  // namespace riva::utils::files
