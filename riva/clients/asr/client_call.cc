/*
 * SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: MIT
 */

#include "client_call.h"

ClientCall::ClientCall(uint32_t corr_id, bool word_time_offsets)
    : corr_id_(corr_id), word_time_offsets_(word_time_offsets)
{
  send_times.reserve(1000);
  recv_times.reserve(1000);
  recv_final_flags.reserve(1000);
}

void
ClientCall::AppendResult(const nr_asr::StreamingRecognitionResult& result)
{
  bool is_final = result.is_final();
  if (latest_result_.final_transcripts.size() < 1) {
    latest_result_.final_transcripts.resize(1);
    latest_result_.final_transcripts[0] = "";
  }

  if (is_final) {
    int num_alternatives = result.alternatives_size();
    latest_result_.final_transcripts.resize(num_alternatives);
    latest_result_.final_scores.resize(num_alternatives);
    for (int a = 0; a < num_alternatives; ++a) {
      // Append to transcript
      latest_result_.final_transcripts[a] += result.alternatives(a).transcript();
      latest_result_.final_scores[a] += result.alternatives(a).confidence();
    }
    if (word_time_offsets_) {
      if (num_alternatives > 0) {
        for (int w = 0; w < result.alternatives(0).words_size(); ++w) {
          latest_result_.final_time_stamps.emplace_back(result.alternatives(0).words(w));
        }
      }
    }
  } else {
    if (result.alternatives_size() > 0) {
      latest_result_.partial_transcript += result.alternatives(0).transcript();
      if (word_time_offsets_) {
        for (int w = 0; w < result.alternatives(0).words_size(); ++w) {
          latest_result_.partial_time_stamps.emplace_back(result.alternatives(0).words(w));
        }
      }
    }
  }
}

void
ClientCall::PrintResult(bool audio_device, std::ofstream& output_file)
{
  std::cout << "-----------------------------------------------------------" << std::endl;

  std::string filename = "microphone";
  if (!audio_device) {
    filename = this->stream->wav->filename;
    std::cout << "File: " << filename << std::endl;
  }

  std::cout << std::endl;
  std::cout << "Final transcripts: " << std::endl;
  if (latest_result_.final_transcripts.size() == 0) {
    output_file << "{\"audio_filepath\": \"" << filename << "\",";
    output_file << "\"text\": \"\"}" << std::endl;
  } else {
    for (uint32_t a = 0; a < latest_result_.final_transcripts.size(); ++a) {
      if (a == 0) {
        output_file << "{\"audio_filepath\": \"" << filename << "\",";
        output_file << "\"text\": \"" << EscapeTranscript(latest_result_.final_transcripts[a])
                    << "\"}" << std::endl;
      }
      std::cout << a << " : " << latest_result_.final_transcripts[a]
                << latest_result_.partial_transcript << std::endl;
    }
    std::cout << std::endl;

    if (word_time_offsets_) {
      std::cout << "Timestamps: " << std::endl;
      std::cout << std::setw(40) << std::left << "Word";
      std::cout << std::setw(16) << std::left << "Start (ms)";
      std::cout << std::setw(16) << std::left << "End (ms)" << std::endl;
      std::cout << std::endl;
      for (uint32_t w = 0; w < latest_result_.final_time_stamps.size(); ++w) {
        auto& word_info = latest_result_.final_time_stamps[w];
        std::cout << std::setw(40) << std::left << word_info.word();
        std::cout << std::setw(16) << std::left << word_info.start_time();
        std::cout << std::setw(16) << std::left << word_info.end_time() << std::endl;
      }

      for (uint32_t w = 0; w < latest_result_.partial_time_stamps.size(); ++w) {
        auto& word_info = latest_result_.partial_time_stamps[w];
        std::cout << std::setw(40) << std::left << word_info.word();
        std::cout << std::setw(16) << std::left << word_info.start_time();
        std::cout << std::setw(16) << std::left << word_info.end_time() << std::endl;
      }
    }
  }
  std::cout << std::endl;
  std::cout << "Audio processed: " << latest_result_.audio_processed << " sec." << std::endl;
  std::cout << "-----------------------------------------------------------" << std::endl;
  std::cout << std::endl;
}
