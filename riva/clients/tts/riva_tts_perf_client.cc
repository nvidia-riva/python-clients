/*
 * SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: MIT
 */

#include <gflags/gflags.h>
#include <glog/logging.h>
#include <grpcpp/grpcpp.h>
#include <strings.h>

#include <algorithm>
#include <chrono>
#include <fstream>
#include <iostream>
#include <iterator>
#include <numeric>
#include <string>
#include <thread>
#include <utility>

#include "riva/clients/utils/grpc.h"
#include "riva/proto/riva_tts.grpc.pb.h"
#include "riva/utils/stamping.h"
#include "riva/utils/wav/wav_writer.h"

#define MAX_SAMPLES 4100 * 256  // for Tacotron2 with 400 character input

using grpc::Status;
using grpc::StatusCode;
namespace nr = nvidia::riva;
namespace nr_tts = nvidia::riva::tts;

DEFINE_string(
    text_file, "", "Text file with list of sentences to be synthesized. Ignored if 'text' is set.");
DEFINE_string(riva_uri, "localhost:50051", "Riva API server URI and port");
DEFINE_int32(rate, 22050, "Sample rate for the TTS output");
DEFINE_bool(online, false, "Whether synthesis should be online or batch");
DEFINE_bool(
    write_output_audio, false,
    "Whether to dump output audio or not. When true, throughput and latency are not reported.");
DEFINE_string(
    language, "en-US",
    "Language code as per [BCP-47](https://www.rfc-editor.org/rfc/bcp/bcp47.txt) language tag.");
DEFINE_string(voice_name, "ljspeech", "Desired voice name");
DEFINE_int32(num_iterations, 1, "Number of times to loop over audio files");
DEFINE_int32(num_parallel_requests, 1, "Number of parallel requests to keep in flight");
DEFINE_int32(throttle_milliseconds, 0, "Number of milliseconds to sleep for between TTS requests");
DEFINE_int32(offset_milliseconds, 0, "Number of milliseconds to offset each parallel TTS requests");
DEFINE_bool(use_ssl, false, "Boolean to control if SSL/TLS encryption should be used.");
DEFINE_string(ssl_cert, "", "Path to SSL client certificatates file");

static const std::string LC_enUS = "en-US";

std::unique_ptr<nr_tts::RivaSpeechSynthesis::Stub>
CreateTTS(std::shared_ptr<grpc::Channel> channel)
{
  std::unique_ptr<nr_tts::RivaSpeechSynthesis::Stub> tts(
      nr_tts::RivaSpeechSynthesis::NewStub(channel));
  return tts;
}


size_t
synthesizeBatch(
    std::unique_ptr<nr_tts::RivaSpeechSynthesis::Stub> tts, std::string text, std::string language,
    uint32_t rate, std::string voice_name, std::string filepath)
{
  // Parse command line arguments.
  nr_tts::SynthesizeSpeechRequest request;
  request.set_text(text);
  request.set_language_code(language);
  request.set_encoding(nr::LINEAR_PCM);
  request.set_sample_rate_hz(rate);
  request.set_voice_name(voice_name);

  // Send text content using Synthesize().
  grpc::ClientContext context;
  nr_tts::SynthesizeSpeechResponse response;

  DLOG(INFO) << "Sending request for input \"" << text << "\".";
  auto start = std::chrono::steady_clock::now();
  grpc::Status rpc_status = tts->Synthesize(&context, request, &response);
  auto end = std::chrono::steady_clock::now();
  DLOG(INFO) << "Received response for input \"" << text << "\".";
  std::chrono::duration<double> elapsed = end - start;

  if (!rpc_status.ok()) {
    // Report the RPC failure.
    std::cerr << rpc_status.error_message() << std::endl;
    std::cerr << "Input was: \'" << text << "\'" << std::endl;
  }

  auto audio = response.audio();
  // Write to WAV file
  if (FLAGS_write_output_audio)
    ::riva::utils::wav::Write(filepath, rate, (float*)audio.data(), audio.length() / sizeof(float));

  return audio.length() / sizeof(float);
}

void
synthesizeOnline(
    std::unique_ptr<nr_tts::RivaSpeechSynthesis::Stub> tts, std::string text, std::string language,
    uint32_t rate, std::string voice_name, double* time_to_first_chunk,
    std::vector<double>* time_to_next_chunk, size_t* num_samples, std::string filepath)
{
  nr_tts::SynthesizeSpeechRequest request;
  request.set_text(text);
  request.set_language_code(language);
  request.set_encoding(nr::LINEAR_PCM);
  request.set_sample_rate_hz(rate);
  request.set_voice_name(voice_name);

  // Send text content using SynthesizeOnline().
  grpc::ClientContext context;

  nr_tts::SynthesizeSpeechResponse chunk;

  auto start = std::chrono::steady_clock::now();
  std::unique_ptr<grpc::ClientReader<nr_tts::SynthesizeSpeechResponse>> reader(
      tts->SynthesizeOnline(&context, request));
  DLOG(INFO) << "Sending request for input \"" << text << "\".";

  std::vector<float> buffer;
  size_t audio_len = 0;

  while (reader->Read(&chunk)) {
    // DLOG(INFO) << "Received chunk with " << chunk.audio().length() << " bytes.";
    // Copy chunk to local buffer
    float* audio_data = (float*)chunk.audio().data();
    size_t len = chunk.audio().length() / sizeof(float);
    std::copy(audio_data, audio_data + len, std::back_inserter(buffer));
    if (audio_len == 0) {
      auto t_next_audio = std::chrono::steady_clock::now();
      std::chrono::duration<double> elapsed_first_audio = t_next_audio - start;
      // std::cerr << "Time to first chunk: " << elapsed_first_audio.count() << " s" << std::endl;
      *time_to_first_chunk = elapsed_first_audio.count();
      start = t_next_audio;
      DLOG(INFO) << "Received first chunk for input \"" << text << "\".";
    } else {
      auto t_next_audio = std::chrono::steady_clock::now();
      std::chrono::duration<double> elapsed_next_audio = t_next_audio - start;
      time_to_next_chunk->push_back(elapsed_next_audio.count());
      start = t_next_audio;
    }
    audio_len += len;
  }
  grpc::Status rpc_status = reader->Finish();
  DLOG(INFO) << "Received all chunks for input \"" << text << "\".";

  if (!rpc_status.ok()) {
    // Report the RPC failure.
    std::cerr << rpc_status.error_message() << std::endl;
    std::cerr << "Input was: \'" << text << "\'" << std::endl;
  } else {
    *num_samples = audio_len;
    if (FLAGS_write_output_audio)
      ::riva::utils::wav::Write(filepath, rate, buffer.data(), buffer.size());
  }
  return;
}

std::vector<double>*
percentiles(std::vector<double> v)
{
  std::vector<double>* results = new std::vector<double>();
  if (!v.empty()) {
    std::sort(v.begin(), v.end());
    results->push_back(v[static_cast<int>(0.90 * v.size())]);
    results->push_back(v[static_cast<int>(0.95 * v.size())]);
    results->push_back(v[static_cast<int>(0.99 * v.size())]);
  }
  return results;
}

int
main(int argc, char** argv)
{
  google::InitGoogleLogging(argv[0]);
  FLAGS_logtostderr = 1;

  std::stringstream str_usage;
  str_usage << "Usage: riva_tts_client " << std::endl;
  str_usage << "           --text_file=<text_file> " << std::endl;
  str_usage << "           --write_output_audio=<true|false> " << std::endl;
  str_usage << "           --riva_uri=<server_name:port> " << std::endl;
  str_usage << "           --rate=<sample_rate> " << std::endl;
  str_usage << "           --language=<language-code> " << std::endl;
  str_usage << "           --voice_name=<voice-name> " << std::endl;
  str_usage << "           --online=<true|false> " << std::endl;
  str_usage << "           --num_parallel_requests=<num-parallel-reqs> " << std::endl;
  str_usage << "           --num_iterations=<num-iterations> " << std::endl;
  str_usage << "           --throttle_milliseconds=<throttle-milliseconds> " << std::endl;
  str_usage << "           --offset_milliseconds=<offset-milliseconds> " << std::endl;
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

  bool flag_set = gflags::GetCommandLineFlagInfoOrDie("riva_uri").is_default;
  const char* riva_uri = getenv("RIVA_URI");

  if (riva_uri && flag_set) {
    std::cout << "Using environment for " << riva_uri << std::endl;
    FLAGS_riva_uri = riva_uri;
  }

  std::string sentence;
  std::vector<std::vector<std::pair<int, std::string>>> sentences;

  auto text_file = FLAGS_text_file;
  if (text_file.length() == 0) {
    std::cerr << "Input text file required." << std::endl;
    return -1;
  }

  // create sentence vectors for each worker
  for (int i = 0; i < FLAGS_num_parallel_requests; i++) {
    std::vector<std::pair<int, std::string>> sentence_vec;
    sentences.push_back(sentence_vec);
  }

  // open text file, load sentences as a vector
  int count = 0;
  for (int i = 0; i < FLAGS_num_iterations; i++) {
    std::ifstream file(text_file);
    while (std::getline(file, sentence)) {
      if (sentence.find("|") != std::string::npos) {
        // sentences are distributed between workers in
        // a round-robin fashion
        sentences[count % FLAGS_num_parallel_requests].push_back(
            make_pair(count, sentence.substr(sentence.find("|") + 1, sentence.length())));
      } else {
        sentences[count % FLAGS_num_parallel_requests].push_back(make_pair(count, sentence));
      }
      count++;
    }
  }

  // Create the GRPC channel before starting timer
  std::shared_ptr<grpc::Channel> grpc_channel;
  try {
    auto creds = riva::clients::CreateChannelCredentials(FLAGS_use_ssl,FLAGS_ssl_cert);
    grpc_channel = riva::clients::CreateChannelBlocking(FLAGS_riva_uri, creds);
  } catch (const std::exception& e) {
    std::cerr << "Error creating GRPC channel: " << e.what() << std::endl;
    std::cerr << "Exiting." << std::endl;
    return 1;
  }

  // Create and start worker threads
  std::vector<std::thread> workers;

  if (FLAGS_online) {
    std::vector<std::vector<double>*> latencies_first_chunk;
    std::vector<std::vector<double>*> latencies_next_chunks;
    std::vector<std::vector<size_t>*> lengths;

    auto start = std::chrono::steady_clock::now();

    for (int i = 0; i < FLAGS_num_parallel_requests; i++) {
      auto time_to_first_chunks = new std::vector<double>();
      latencies_first_chunk.push_back(time_to_first_chunks);
      auto time_to_next_chunks = new std::vector<double>();
      latencies_next_chunks.push_back(time_to_next_chunks);
      auto length = new std::vector<size_t>();
      lengths.push_back(length);
      workers.push_back(std::thread([&, i]() {
        usleep(i * FLAGS_offset_milliseconds * 1000);
        auto start_time = std::chrono::steady_clock::now();

        for (size_t s = 0; s < sentences[i].size(); s++) {
          auto current_time = std::chrono::steady_clock::now();
          double diff_time =
              std::chrono::duration<double, std::milli>(current_time - start_time).count();
          double wait_time = (s + 1) * FLAGS_throttle_milliseconds - diff_time;

          // To nanoseconds
          wait_time *= 1.e3;
          wait_time = std::max(wait_time, 0.);

          // Round to nearest integer
          wait_time = wait_time + 0.5 - (wait_time < 0);
          int64_t usecs = (int64_t)wait_time;
          // Sleep
          if (usecs > 0) {
            usleep(usecs);
          }

          auto tts = CreateTTS(grpc_channel);
          double time_to_first_chunk = 0.;
          auto time_to_next_chunk = new std::vector<double>();
          size_t num_samples = 0;
          synthesizeOnline(
              std::move(tts), sentences[i][s].second, FLAGS_language, FLAGS_rate, FLAGS_voice_name,
              &time_to_first_chunk, time_to_next_chunk, &num_samples,
              std::to_string(sentences[i][s].first) + ".wav");
          latencies_first_chunk[i]->push_back(time_to_first_chunk);
          latencies_next_chunks[i]->insert(
              latencies_next_chunks[i]->end(), time_to_next_chunk->begin(),
              time_to_next_chunk->end());
          lengths[i]->push_back(num_samples);
        }
      }));
    }

    std::for_each(workers.begin(), workers.end(), [](std::thread& worker) { worker.join(); });
    auto end = std::chrono::steady_clock::now();
    std::chrono::duration<double> elapsed = end - start;

    if (!FLAGS_write_output_audio) {
      std::vector<double> first_chunks_all_threads;
      std::vector<double> next_chunks_all_threads;
      std::vector<double> lengths_all_threads;

      for (int i = 0; i < FLAGS_num_parallel_requests; i++) {
        // concatenate all result vectors
        first_chunks_all_threads.insert(
            first_chunks_all_threads.end(), latencies_first_chunk[i]->begin(),
            latencies_first_chunk[i]->end());
        next_chunks_all_threads.insert(
            next_chunks_all_threads.end(), latencies_next_chunks[i]->begin(),
            latencies_next_chunks[i]->end());
        lengths_all_threads.insert(
            lengths_all_threads.end(), lengths[i]->begin(), lengths[i]->end());
      }

      if (!first_chunks_all_threads.empty() && !next_chunks_all_threads.empty()) {
        auto results_first_chunk = percentiles(first_chunks_all_threads);
        auto results_next_chunk = percentiles(next_chunks_all_threads);
        auto total_num_samples =
            std::accumulate(lengths_all_threads.begin(), lengths_all_threads.end(), 0.);

        std::cout << "Latencies: " << std::endl;
        std::cout << "First audio - average: "
                  << std::accumulate(
                         first_chunks_all_threads.begin(), first_chunks_all_threads.end(), 0.) /
                         first_chunks_all_threads.size()
                  << std::endl;
        std::cout << "First audio - P90: " << results_first_chunk->at(0) << std::endl;
        std::cout << "First audio - P95: " << results_first_chunk->at(1) << std::endl;
        std::cout << "First audio - P99: " << results_first_chunk->at(2) << std::endl;

        std::cout << "Chunk - average: "
                  << std::accumulate(
                         next_chunks_all_threads.begin(), next_chunks_all_threads.end(), 0.) /
                         next_chunks_all_threads.size()
                  << std::endl;
        std::cout << "Chunk - P90: " << results_next_chunk->at(0) << std::endl;
        std::cout << "Chunk - P95: " << results_next_chunk->at(1) << std::endl;
        std::cout << "Chunk - P99: " << results_next_chunk->at(2) << std::endl;

        std::cout << "Throughput (RTF): " << (total_num_samples / FLAGS_rate) / elapsed.count()
                  << std::endl;
      } else {
        std::cerr << "ERROR: Metrics vector is empty, check previous error messages for details."
                  << std::endl;
      }
    }
  } else {
    std::vector<std::vector<size_t>*> results_num_samples;
    auto start = std::chrono::steady_clock::now();
    for (int i = 0; i < FLAGS_num_parallel_requests; i++) {
      auto results_num_samples_thread = new std::vector<size_t>();
      results_num_samples.push_back(results_num_samples_thread);
      workers.push_back(std::thread([&, i]() {
        for (size_t s = 0; s < sentences[i].size(); s++) {
          auto tts = CreateTTS(grpc_channel);
          size_t num_samples = synthesizeBatch(
              std::move(tts), sentences[i][s].second, FLAGS_language, FLAGS_rate, FLAGS_voice_name,
              std::to_string(sentences[i][s].first) + ".wav");
          results_num_samples[i]->push_back(num_samples);
        }
      }));
    }
    std::for_each(workers.begin(), workers.end(), [](std::thread& worker) { worker.join(); });
    auto end = std::chrono::steady_clock::now();
    std::chrono::duration<double> elapsed = end - start;

    if (!FLAGS_write_output_audio) {
      double total_num_samples = 0;
      for (int i = 0; i < FLAGS_num_parallel_requests; i++) {
        total_num_samples +=
            std::accumulate(results_num_samples[i]->begin(), results_num_samples[i]->end(), 0.);
      }
      std::cout << "Average RTF: " << (total_num_samples / FLAGS_rate) / elapsed.count()
                << std::endl;
    }
  }
  return 0;
}
