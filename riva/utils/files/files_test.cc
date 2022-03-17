/*
 * SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: MIT
 */

#include "files.h"

#include <gmock/gmock.h>
#include <gtest/gtest.h>

#include <fstream>
#include <iostream>

using namespace ::testing;

namespace riva::utils::files {

TEST(FilesUtils, ReadFileContentAsStringNotExist)
{
  std::string filename = "i_dont_exist";
  try {
    ReadFileContentAsString(filename);
    FAIL() << "Expected runtime error for non-existant file";
  }
  catch (std::runtime_error& e) {
    EXPECT_THAT(e.what(), testing::HasSubstr("does not exist"));
  }
  catch (...) {
    FAIL() << "Expected runtime error";
  }
}

TEST(FilesUtils, ReadFileContentAsString)
{
  std::string filename = "test.txt";
  std::string file_content = " this is a test\n another\n";

  std::ofstream myfile;
  myfile.open(filename);
  myfile << file_content;
  myfile.close();

  auto output = ReadFileContentAsString(filename);
  EXPECT_EQ(output, file_content);
}
}  // namespace riva::utils::files
