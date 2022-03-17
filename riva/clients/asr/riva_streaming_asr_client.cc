/*
 * SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: MIT
 */

#include <alsa/asoundlib.h>
#include <gflags/gflags.h>
#include <glog/logging.h>
#include <grpcpp/grpcpp.h>
#include <strings.h>

#include <atomic>
#include <chrono>
#include <cmath>
#include <csignal>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <iterator>
#include <mutex>
#include <numeric>
#include <queue>
#include <sstream>
#include <string>
#include <thread>

#include "client_call.h"
#include "riva/clients/utils/grpc.h"
#include "riva/proto/riva_asr.grpc.pb.h"
#include "riva/utils/files/files.h"
#include "riva/utils/stamping.h"
#include "riva/utils/wav/wav_reader.h"
#include "riva_asr_client_helper.h"
#include "streaming_recognize_client.h"

using grpc::Status;
using grpc::StatusCode;
namespace nr = nvidia::riva;
namespace nr_asr = nvidia::riva::asr;

bool g_request_exit = false;

DEFINE_string(
    audio_file, "", "Folder that contains audio files to transcribe or individual audio file name");
DEFINE_int32(
    max_alternatives, 1,
    "Maximum number of alternative transcripts to return (up to limit configured on server)");
DEFINE_bool(automatic_punctuation, true, "Flag that controls if transcript should be punctuated");
DEFINE_bool(word_time_offsets, true, "Flag that controls if word time stamps are requested");
DEFINE_bool(
    simulate_realtime, false, "Flag that controls if audio files should be sent in realtime");
DEFINE_string(audio_device, "", "Name of audio device to use");
DEFINE_string(riva_uri, "localhost:50051", "URI to access riva-server");
DEFINE_int32(num_iterations, 1, "Number of times to loop over audio files");
DEFINE_int32(num_parallel_requests, 1, "Number of parallel requests to keep in flight");
DEFINE_int32(chunk_duration_ms, 100, "Chunk duration in milliseconds");
DEFINE_bool(print_transcripts, true, "Print final transcripts");
DEFINE_bool(interim_results, true, "Print intermediate transcripts");
DEFINE_string(
    output_filename, "final_transcripts.json",
    "Filename of .json file containing output transcripts");
DEFINE_string(model_name, "", "Name of the TRTIS model to use");
DEFINE_string(language_code, "en-US", "Language code of the model to use");
DEFINE_string(boosted_words_file, "", "File with a list of words to boost. One line per word.");
DEFINE_double(boosted_words_score, 10., "Score by which to boost the boosted words");
DEFINE_bool(
    verbatim_transcripts, true,
    "True returns text exactly as it was said with no normalization.  False applies text inverse "
    "normalization");
DEFINE_string(ssl_cert, "", "Path to SSL client certificatates file");
DEFINE_bool(use_ssl, false, "Boolean to control if SSL/TLS encryption should be used.");

void
signal_handler(int signal_num)
{
  static int count;
  if (count > 0) {
    std::cout << "Force exit\n";
    exit(1);
  }
  std::cout << "Stopping capture\n";
  g_request_exit = true;
  count++;
}

int
main(int argc, char** argv)
{
  google::InitGoogleLogging(argv[0]);
  FLAGS_logtostderr = 1;

  std::stringstream str_usage;
  str_usage << "Usage: riva_streaming_asr_client " << std::endl;
  str_usage << "           --audio_file=<filename or folder> " << std::endl;
  str_usage << "           --audio_device=<device_id (such as hw:5,0)> " << std::endl;
  str_usage << "           --automatic_punctuation=<true|false>" << std::endl;
  str_usage << "           --max_alternatives=<integer>" << std::endl;
  str_usage << "           --word_time_offsets=<true|false>" << std::endl;
  str_usage << "           --riva_uri=<server_name:port> " << std::endl;
  str_usage << "           --chunk_duration_ms=<integer> " << std::endl;
  str_usage << "           --interim_results=<true|false> " << std::endl;
  str_usage << "           --simulate_realtime=<true|false> " << std::endl;
  str_usage << "           --num_iterations=<integer> " << std::endl;
  str_usage << "           --num_parallel_requests=<integer> " << std::endl;
  str_usage << "           --print_transcripts=<true|false> " << std::endl;
  str_usage << "           --output_filename=<string>" << std::endl;
  str_usage << "           --verbatim_transcripts=<true|false>" << std::endl;
  str_usage << "           --language_code=<bcp 47 language code (such as en-US)>" << std::endl;
  str_usage << "           --boosted_words_file=<string>" << std::endl;
  str_usage << "           --boosted_words_score=<float>" << std::endl;
  str_usage << "           --ssl_cert=<filename>" << std::endl;
  str_usage << "           --use_ssl=<true|false>" << std::endl;
  gflags::SetUsageMessage(str_usage.str());
  gflags::SetVersionString(::riva::utils::kBuildScmRevision);

  if (argc < 2) {
    std::cout << gflags::ProgramUsage();
    return 1;
  }

  std::signal(SIGINT, signal_handler);
  gflags::ParseCommandLineFlags(&argc, &argv, true);

  if (argc > 1) {
    std::cout << gflags::ProgramUsage();
    return 1;
  }

  if (FLAGS_max_alternatives < 1) {
    std::cerr << "max_alternatives must be greater than or equal to 1." << std::endl;
    return 1;
  }

  bool flag_set = gflags::GetCommandLineFlagInfoOrDie("riva_uri").is_default;
  const char* riva_uri = getenv("RIVA_URI");

  if (riva_uri && flag_set) {
    std::cout << "Using environment for " << riva_uri << std::endl;
    FLAGS_riva_uri = riva_uri;
  }

  std::shared_ptr<grpc::Channel> grpc_channel;
  try {
    auto creds = riva::clients::CreateChannelCredentials(FLAGS_use_ssl,FLAGS_ssl_cert);
    grpc_channel = riva::clients::CreateChannelBlocking(FLAGS_riva_uri, creds);
  } catch (const std::exception& e) {
    std::cerr << "Error creating GRPC channel: " << e.what() << std::endl;
    std::cerr << "Exiting." << std::endl;
    return 1;
  }

  StreamingRecognizeClient recognize_client(
      grpc_channel, FLAGS_num_parallel_requests, FLAGS_language_code, FLAGS_max_alternatives,
      FLAGS_word_time_offsets, FLAGS_automatic_punctuation,
      /* separate_recognition_per_channel*/ false, FLAGS_print_transcripts, FLAGS_chunk_duration_ms,
      FLAGS_interim_results, FLAGS_output_filename, FLAGS_model_name, FLAGS_simulate_realtime,
      FLAGS_verbatim_transcripts, FLAGS_boosted_words_file, FLAGS_boosted_words_score);

  if (FLAGS_audio_file.size()) {
    return recognize_client.DoStreamingFromFile(
        FLAGS_audio_file, FLAGS_num_iterations, FLAGS_num_parallel_requests);

  } else if (FLAGS_audio_device.size()) {
    if (FLAGS_num_parallel_requests != 1) {
      std::cout << "num_parallel_requests must be set to 1 with microphone input" << std::endl;
      return 1;
    }

    if (!FLAGS_interim_results) {
      std::cout << "interim_results must be set to true when streaming from microphone input"
                << std::endl;
      return 1;
    }

    if (!FLAGS_print_transcripts) {
      std::cout << "print_transcripts must be set to true when streaming from microphone input"
                << std::endl;
      return 1;
    }

    if (FLAGS_simulate_realtime) {
      std::cout << "simulate_realtime must be set to false with microphone input" << std::endl;
      return 1;
    }

    if (FLAGS_num_iterations != 1) {
      std::cout << "num_iterations must be set to 1 with microphone input" << std::endl;
      return 1;
    }

    return recognize_client.DoStreamingFromMicrophone(FLAGS_audio_device, g_request_exit);

  } else {
    std::cout << "No audio files or audio device specified, exiting" << std::endl;
  }

  return 0;
}
