/*
 * SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: MIT
 */

#include <gflags/gflags.h>
#include <glog/logging.h>
#include <grpcpp/grpcpp.h>
#include <strings.h>

#include <chrono>
#include <fstream>
#include <iostream>
#include <iterator>
#include <string>

#include "absl/time/time.h"
#include "riva/clients/utils/grpc.h"
#include "riva/proto/riva_tts.grpc.pb.h"
#include "riva/utils/stamping.h"
#include "riva/utils/wav/wav_writer.h"

using grpc::Status;
using grpc::StatusCode;
namespace nr = nvidia::riva;
namespace nr_tts = nvidia::riva::tts;

DEFINE_string(text, "", "Text to be synthesized");
DEFINE_string(audio_file, "output.wav", "Output file");
DEFINE_string(riva_uri, "localhost:50051", "Riva API server URI and port");
DEFINE_int32(rate, 22050, "Sample rate for the TTS output");
DEFINE_bool(online, false, "Whether synthesis should be online or batch");
DEFINE_string(
    language, "en-US",
    "Language code as per [BCP-47](https://www.rfc-editor.org/rfc/bcp/bcp47.txt) language tag.");
DEFINE_string(voice_name, "ljspeech", "Desired voice name");
DEFINE_bool(use_ssl, false, "Boolean to control if SSL/TLS encryption should be used.");
DEFINE_string(ssl_cert, "", "Path to SSL client certificatates file");

static const std::string LC_enUS = "en-US";

int
main(int argc, char** argv)
{
  google::InitGoogleLogging(argv[0]);
  FLAGS_logtostderr = 1;

  std::stringstream str_usage;
  str_usage << "Usage: riva_tts_client " << std::endl;
  str_usage << "           --text=<text> " << std::endl;
  str_usage << "           --audio_file=<filename> " << std::endl;
  str_usage << "           --riva_uri=<server_name:port> " << std::endl;
  str_usage << "           --rate=<sample_rate> " << std::endl;
  str_usage << "           --language=<language-code> " << std::endl;
  str_usage << "           --voice_name=<voice-name> " << std::endl;
  str_usage << "           --online=<true|false> " << std::endl;
  str_usage << "           --use_ssl=<true|false>" << std::endl;
  str_usage << "           --ssl_cert=<filename>" << std::endl;
  gflags::SetUsageMessage(str_usage.str());
  gflags::SetVersionString(::riva::utils::kBuildScmRevision);

  if (argc < 2) {
    std::cout << gflags::ProgramUsage();
    return 1;
  }

  gflags::ParseCommandLineFlags(&argc, &argv, true);

  if (argc > 1) {
    std::cout << gflags::ProgramUsage();
    return 1;
  }

  auto text = FLAGS_text;
  if (text.length() == 0) {
    std::cerr << "Input text cannot be empty." << std::endl;
    return -1;
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

  std::unique_ptr<nr_tts::RivaSpeechSynthesis::Stub> tts(
      nr_tts::RivaSpeechSynthesis::NewStub(grpc_channel));

  // Parse command line arguments.
  nr_tts::SynthesizeSpeechRequest request;
  request.set_text(text);
  request.set_language_code(FLAGS_language);
  request.set_encoding(nr::LINEAR_PCM);
  request.set_sample_rate_hz(FLAGS_rate);
  request.set_voice_name(FLAGS_voice_name);

  // Send text content using Synthesize().
  grpc::ClientContext context;
  nr_tts::SynthesizeSpeechResponse response;

  if (!FLAGS_online) {  // batch inference
    auto start = std::chrono::steady_clock::now();
    grpc::Status rpc_status = tts->Synthesize(&context, request, &response);
    auto end = std::chrono::steady_clock::now();
    std::chrono::duration<double> elapsed = end - start;
    std::cerr << "Request time: " << elapsed.count() << " s" << std::endl;

    if (!rpc_status.ok()) {
      // Report the RPC failure.
      std::cerr << rpc_status.error_message() << std::endl;
      std::cerr << "Input was: \'" << text << "\'" << std::endl;
      return -1;
    }

    auto audio = response.audio();
    // Write to WAV file
    std::cerr << "Got " << audio.length() << " bytes back from server" << std::endl;
    ::riva::utils::wav::Write(
        FLAGS_audio_file, FLAGS_rate, (float*)audio.data(), audio.length() / sizeof(float));
  } else {  // online inference
    std::vector<float> buffer;
    size_t audio_len = 0;
    nr_tts::SynthesizeSpeechResponse chunk;
    auto start = std::chrono::steady_clock::now();
    std::unique_ptr<grpc::ClientReader<nr_tts::SynthesizeSpeechResponse>> reader(
        tts->SynthesizeOnline(&context, request));
    while (reader->Read(&chunk)) {
      // Copy chunk to local buffer
      if (audio_len == 0) {
        auto t_first_audio = std::chrono::steady_clock::now();
        std::chrono::duration<double> elapsed_first_audio = t_first_audio - start;
        std::cerr << "Time to first chunk: " << elapsed_first_audio.count() << " s" << std::endl;
      }
      float* audio_data = (float*)chunk.audio().data();
      size_t len = chunk.audio().length() / sizeof(float);
      std::copy(audio_data, audio_data + len, std::back_inserter(buffer));
      audio_len += len;
    }
    grpc::Status rpc_status = reader->Finish();
    auto end = std::chrono::steady_clock::now();
    std::chrono::duration<double> elapsed_total = end - start;
    std::cerr << "Streaming time: " << elapsed_total.count() << " s" << std::endl;

    if (!rpc_status.ok()) {
      // Report the RPC failure.
      std::cerr << rpc_status.error_message() << std::endl;
      std::cerr << "Input was: \'" << text << "\'" << std::endl;
      return -1;
    }

    ::riva::utils::wav::Write(FLAGS_audio_file, FLAGS_rate, buffer.data(), buffer.size());
  }
  return 0;
}
