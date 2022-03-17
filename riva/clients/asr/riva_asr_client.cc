/*
 * SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: MIT
 */

#include <alsa/asoundlib.h>
#include <gflags/gflags.h>
#include <glog/logging.h>
#include <grpcpp/grpcpp.h>
#include <strings.h>

#include <chrono>
#include <cmath>
#include <csignal>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <iterator>
#include <mutex>
#include <numeric>
#include <sstream>
#include <string>
#include <thread>

#include "riva/clients/utils/grpc.h"
#include "riva/proto/riva_asr.grpc.pb.h"
#include "riva/utils/files/files.h"
#include "riva/utils/stamping.h"
#include "riva/utils/wav/wav_reader.h"
#include "riva_asr_client_helper.h"

using grpc::Status;
using grpc::StatusCode;
namespace nr = nvidia::riva;
namespace nr_asr = nvidia::riva::asr;

#define clear_screen() printf("\033[H\033[J")
#define gotoxy(x, y) printf("\033[%d;%dH", (y), (x))

DEFINE_string(
    audio_file, "", "Folder that contains audio files to transcribe or individual audio file name");
DEFINE_int32(
    max_alternatives, 1,
    "Maximum number of alternative transcripts to return (up to limit configured on server)");
DEFINE_bool(automatic_punctuation, true, "Flag that controls if transcript should be punctuated");
DEFINE_bool(word_time_offsets, true, "Flag that controls if word time stamps are requested");
DEFINE_string(riva_uri, "localhost:50051", "URI to access riva-server");
DEFINE_int32(num_iterations, 1, "Number of times to loop over audio files");
DEFINE_int32(num_parallel_requests, 10, "Number of parallel requests to keep in flight");
DEFINE_bool(print_transcripts, true, "Print final transcripts");
DEFINE_string(output_filename, "", "Filename to write output transcripts");
DEFINE_string(model_name, "", "Name of the TRTIS model to use");
DEFINE_bool(output_ctm, false, "If true, output format should be NIST CTM");
DEFINE_string(language_code, "en-US", "Language code of the model to use");
DEFINE_string(boosted_words_file, "", "File with a list of words to boost. One line per word.");
DEFINE_double(boosted_words_score, 10., "Score by which to boost the boosted words");
DEFINE_bool(
    verbatim_transcripts, true,
    "True returns text exactly as it was said with no normalization.  False applies text inverse "
    "normalization");
DEFINE_string(ssl_cert, "", "Path to SSL client certificatates file");
DEFINE_bool(use_ssl, false, "Boolean to control if SSL/TLS encryption should be used.");

class RecognizeClient {
 public:
  RecognizeClient(
      std::shared_ptr<grpc::Channel> channel, const std::string& language_code,
      int32_t max_alternatives, bool word_time_offsets, bool automatic_punctuation,
      bool separate_recognition_per_channel, bool print_transcripts, std::string output_filename,
      std::string model_name, bool ctm, bool verbatim_transcripts,
      const std::string& boosted_words_file, float boosted_words_score)
      : stub_(nr_asr::RivaSpeechRecognition::NewStub(channel)), language_code_(language_code),
        max_alternatives_(max_alternatives), word_time_offsets_(word_time_offsets),
        automatic_punctuation_(automatic_punctuation),
        separate_recognition_per_channel_(separate_recognition_per_channel),
        print_transcripts_(print_transcripts), done_sending_(false), num_requests_(0),
        num_responses_(0), num_failed_requests_(0), total_audio_processed_(0.),
        model_name_(model_name), output_filename_(output_filename),
        verbatim_transcripts_(verbatim_transcripts), boosted_words_score_(boosted_words_score)
  {
    if (!output_filename.empty()) {
      output_file_.open(output_filename);
      if (ctm) {
        write_fn_ = &RecognizeClient::WriteCTM;
      } else {
        write_fn_ = &RecognizeClient::WriteJSON;
      }
    }

    if (!boosted_words_file.empty()) {
      std::ifstream infile(boosted_words_file);
      std::string boosted_word;
      while (infile >> boosted_word) {
        boosted_words_.push_back(boosted_word);
      }
    }
  }

  ~RecognizeClient()
  {
    if (output_file_.is_open()) {
      output_file_.close();
    }
  }

  uint32_t NumActiveTasks()
  {
    std::lock_guard<std::mutex> lock(mutex_);
    return curr_tasks_.size();
  }

  uint32_t NumFailedRequests() { return num_failed_requests_; }

  float TotalAudioProcessed() { return total_audio_processed_; }

  void WriteCTM(const nr_asr::SpeechRecognitionResult& result, const std::string& filename)
  {
    std::string bname(basename(filename.c_str()));
    std::string side = (bname.find("-B-") == std::string::npos) ? "A" : "B";
    if (result.alternatives_size() > 0) {
      // we only use the top result for now
      auto hypothesis = result.alternatives(0);
      for (int w = 0; w < hypothesis.words_size(); ++w) {
        auto& word_info = hypothesis.words(w);
        output_file_ << bname << " " << side /* channel */ << " "
                     << (float)word_info.start_time() / 1000. << " "
                     << (float)(word_info.end_time() - word_info.start_time()) / 1000. << " "
                     << word_info.word() << " " << -1.0 /* confidence */ << std::endl;
      }
    }
  }

  void WriteJSON(const nr_asr::SpeechRecognitionResult& result, const std::string& filename)
  {
    if (result.alternatives_size() == 0) {
      output_file_ << "{\"audio_filepath\": \"" << filename << "\",";
      output_file_ << "\"text\": \"\"}" << std::endl;
    } else {
      for (int a = 0; a < result.alternatives_size(); ++a) {
        if (a == 0) {
          output_file_ << "{\"audio_filepath\": \"" << filename << "\",";
          output_file_ << "\"text\": \"" << EscapeTranscript(result.alternatives(a).transcript())
                       << "\"}" << std::endl;
        }
      }
    }
  }

  void PrintResults(const nr_asr::SpeechRecognitionResult& result, const std::string& filename)
  {
    std::cout << "-----------------------------------------------------------" << std::endl;
    std::cout << "File: " << filename << std::endl;
    std::cout << std::endl;
    std::cout << "Final transcripts: " << std::endl;

    if (result.alternatives_size() != 0) {
      for (int a = 0; a < result.alternatives_size(); ++a) {
        std::cout << a << " : " << result.alternatives(a).transcript() << std::endl;
      }
      std::cout << std::endl;

      if (word_time_offsets_) {
        std::cout << "Timestamps: " << std::endl;
        std::cout << std::setw(40) << std::left << "Word";
        std::cout << std::setw(16) << std::left << "Start (ms)";
        std::cout << std::setw(16) << std::left << "End (ms)" << std::endl;
        for (int w = 0; w < result.alternatives(0).words_size(); ++w) {
          auto& word_info = result.alternatives(0).words(w);
          std::cout << std::setw(40) << std::left << word_info.word();
          std::cout << std::setw(16) << std::left << word_info.start_time();
          std::cout << std::setw(16) << std::left << word_info.end_time() << std::endl;
        }
      }
    }
    std::cout << "Audio processed: " << result.audio_processed() << " sec." << std::endl;
    std::cout << "-----------------------------------------------------------" << std::endl;
    std::cout << std::endl;
  }

  void PrintStats()
  {
    std::sort(latencies_.begin(), latencies_.end());
    double nresultsf = static_cast<double>(latencies_.size());
    size_t per50i = static_cast<size_t>(std::floor(50. * nresultsf / 100.));
    size_t per90i = static_cast<size_t>(std::floor(90. * nresultsf / 100.));
    size_t per95i = static_cast<size_t>(std::floor(95. * nresultsf / 100.));
    size_t per99i = static_cast<size_t>(std::floor(99. * nresultsf / 100.));

    double median = latencies_[per50i];
    double lat_90 = latencies_[per90i];
    double lat_95 = latencies_[per95i];
    double lat_99 = latencies_[per99i];

    double avg = std::accumulate(latencies_.begin(), latencies_.end(), 0.0) / latencies_.size();

    std::cout << std::setprecision(5);
    std::cout << "Latencies (ms):\n";
    std::cout << "\t\tMedian\t\t90th\t\t95th\t\t99th\t\tAvg\n";
    std::cout << "\t\t" << median << "\t\t" << lat_90 << "\t\t" << lat_95 << "\t\t" << lat_99
              << "\t\t" << avg << std::endl;
  }

  void DoneSending()
  {
    done_sending_ = true;
    return;
  }

  // Assembles the client's payload and sends it to the server.
  void Recognize(std::unique_ptr<Stream> stream)
  {
    // Data we are sending to the server.
    nr_asr::RecognizeRequest request;

    std::shared_ptr<WaveData> wav = stream->wav;

    auto config = request.mutable_config();
    config->set_sample_rate_hertz(wav->sample_rate);
    config->set_encoding(wav->encoding);
    config->set_language_code(language_code_);
    config->set_max_alternatives(max_alternatives_);
    config->set_audio_channel_count(wav->channels);
    config->set_enable_word_time_offsets(word_time_offsets_);
    config->set_enable_automatic_punctuation(automatic_punctuation_);
    config->set_verbatim_transcripts(verbatim_transcripts_);
    config->set_enable_separate_recognition_per_channel(separate_recognition_per_channel_);
    auto custom_config = config->mutable_custom_configuration();
    (*custom_config)["test_key"] = "test_value";

    if (model_name_ != "") {
      config->set_model(model_name_);
    }

    nr_asr::SpeechContext* speech_context = config->add_speech_contexts();
    *(speech_context->mutable_phrases()) = {boosted_words_.begin(), boosted_words_.end()};
    speech_context->set_boost(boosted_words_score_);


    request.set_audio(&wav->data[0], wav->data.size());

    {
      std::lock_guard<std::mutex> lock(mutex_);
      curr_tasks_.emplace(stream->corr_id);
      num_requests_++;
    }

    // Call object to store rpc data
    AsyncClientCall* call = new AsyncClientCall;

    call->stream = std::move(stream);

    // stub_->PrepareAsyncSayHello() creates an RPC object, returning
    // an instance to store in "call" but does not actually start the RPC
    // Because we are using the asynchronous API, we need to hold on to
    // the "call" instance in order to get updates on the ongoing RPC.
    call->response_reader = stub_->PrepareAsyncRecognize(&call->context, request, &cq_);

    call->start_time = std::chrono::steady_clock::now();
    // StartCall initiates the RPC call
    call->response_reader->StartCall();

    // Request that, upon completion of the RPC, "reply" be updated with the
    // server's response; "status" with the indication of whether the operation
    // was successful. Tag the request with the memory address of the call object.
    call->response_reader->Finish(&call->response, &call->status, (void*)call);
  }

  // Loop while listening for completed responses.
  // Prints out the response from the server.
  void AsyncCompleteRpc()
  {
    void* got_tag;
    bool ok = false;

    // Block until the next result is available in the completion queue "cq".
    bool stop_flag = false;
    while (!stop_flag && cq_.Next(&got_tag, &ok)) {
      // The tag in this example is the memory location of the call object
      AsyncClientCall* call = static_cast<AsyncClientCall*>(got_tag);

      // Verify that the request was completed successfully. Note that "ok"
      // corresponds solely to the request for updates introduced by Finish().
      GPR_ASSERT(ok);

      if (call->status.ok()) {
        auto end_time = std::chrono::steady_clock::now();
        double lat = std::chrono::duration<double, std::milli>(end_time - call->start_time).count();
        latencies_.push_back(lat);
        const auto& result = call->response.results(0);
        total_audio_processed_ += result.audio_processed();

        if (print_transcripts_) {
          PrintResults(result, call->stream->wav->filename);
        }
        if (!output_filename_.empty()) {
          (this->*write_fn_)(result, call->stream->wav->filename);
        }
      } else {
        std::cout << "RPC failed: " << call->status.error_message() << std::endl;
        // This means that receiving thread will never finish
        num_failed_requests_++;
      }

      // Remove the element from the map
      {
        std::lock_guard<std::mutex> lock(mutex_);
        curr_tasks_.erase(call->stream->corr_id);
        num_responses_++;
      }


      // Once we're complete, deallocate the call object.
      delete call;

      if (num_responses_ == num_requests_ && done_sending_) {
        stop_flag = true;
        std::cout << "Done processing " << num_responses_ << " responses" << std::endl;
      }
    }
  }

 private:
  // struct for keeping state and data information
  struct AsyncClientCall {
    // Container for the data we expect from the server.
    nr_asr::RecognizeResponse response;

    // Context for the client. It could be used to convey extra information to
    // the server and/or tweak certain RPC behaviors.
    grpc::ClientContext context;

    // Storage for the status of the RPC upon completion.
    grpc::Status status;

    std::unique_ptr<grpc::ClientAsyncResponseReader<nr_asr::RecognizeResponse>> response_reader;

    std::unique_ptr<Stream> stream;
    std::chrono::time_point<std::chrono::steady_clock> start_time;
  };

  // Out of the passed in Channel comes the stub, stored here, our view of the
  // server's exposed services.
  std::unique_ptr<nr_asr::RivaSpeechRecognition::Stub> stub_;

  // The producer-consumer queue we use to communicate asynchronously with the
  // gRPC runtime.
  grpc::CompletionQueue cq_;

  std::set<uint32_t> curr_tasks_;
  std::vector<double> latencies_;

  std::string language_code_;
  int32_t max_alternatives_;
  int32_t channels_;
  bool word_time_offsets_;
  bool automatic_punctuation_;
  bool separate_recognition_per_channel_;
  bool print_transcripts_;


  std::mutex mutex_;
  bool done_sending_;
  uint32_t num_requests_;
  uint32_t num_responses_;
  uint32_t num_failed_requests_;

  std::ofstream output_file_;

  float total_audio_processed_;

  std::string model_name_;
  std::string output_filename_;
  bool verbatim_transcripts_;

  std::vector<std::string> boosted_words_;
  float boosted_words_score_;
  void (RecognizeClient::*write_fn_)(
      const nr_asr::SpeechRecognitionResult& result, const std::string& filename);
};

int
main(int argc, char** argv)
{
  google::InitGoogleLogging(argv[0]);
  FLAGS_logtostderr = 1;

  std::stringstream str_usage;
  str_usage << "Usage: riva_asr_client " << std::endl;
  str_usage << "           --audio_file=<filename or folder> " << std::endl;
  str_usage << "           --automatic_punctuation=<true|false>" << std::endl;
  str_usage << "           --max_alternatives=<integer>" << std::endl;
  str_usage << "           --word_time_offsets=<true|false>" << std::endl;
  str_usage << "           --riva_uri=<server_name:port> " << std::endl;
  str_usage << "           --num_iterations=<integer> " << std::endl;
  str_usage << "           --num_parallel_requests=<integer> " << std::endl;
  str_usage << "           --print_transcripts=<true|false> " << std::endl;
  str_usage << "           --output_filename=<string>" << std::endl;
  str_usage << "           --output-ctm=<true|false>" << std::endl;
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

  RecognizeClient recognize_client(
      grpc_channel, FLAGS_language_code, FLAGS_max_alternatives, FLAGS_word_time_offsets,
      FLAGS_automatic_punctuation, /* separate_recognition_per_channel*/ false,
      FLAGS_print_transcripts, FLAGS_output_filename, FLAGS_model_name, FLAGS_output_ctm,
      FLAGS_verbatim_transcripts, FLAGS_boosted_words_file, (float)FLAGS_boosted_words_score);

  // Preload all wav files, sort by size to reduce tail effects
  std::vector<std::shared_ptr<WaveData>> all_wav;
  LoadWavData(all_wav, FLAGS_audio_file);

  if (all_wav.size() == 0) {
    std::cout << "Exiting.." << std::endl;
    return 1;
  }

  uint32_t all_wav_max = all_wav.size() * FLAGS_num_iterations;
  std::vector<std::shared_ptr<WaveData>> all_wav_repeated;
  all_wav_repeated.reserve(all_wav_max);
  for (uint32_t file_id = 0; file_id < all_wav.size(); file_id++) {
    for (int iter = 0; iter < FLAGS_num_iterations; iter++) {
      all_wav_repeated.push_back(all_wav[file_id]);
    }
  }

  // Spawn reader thread that loops indefinitely
  std::thread thread_ = std::thread(&RecognizeClient::AsyncCompleteRpc, &recognize_client);

  // Ensure there's also num_parallel_requests in flight
  uint32_t all_wav_i = 0;
  auto start_time = std::chrono::steady_clock::now();
  while (true) {
    while (recognize_client.NumActiveTasks() < (uint32_t)FLAGS_num_parallel_requests &&
           all_wav_i < all_wav_max) {
      std::unique_ptr<Stream> stream(new Stream(all_wav_repeated[all_wav_i], all_wav_i));
      recognize_client.Recognize(std::move(stream));
      ++all_wav_i;
    }

    if (all_wav_i == all_wav_max) {
      break;
    }
  }

  recognize_client.DoneSending();
  thread_.join();

  if (recognize_client.NumFailedRequests()) {
    std::cout << "Some requests failed to complete properly, not printing performance stats"
              << std::endl;
  } else {
    recognize_client.PrintStats();

    auto current_time = std::chrono::steady_clock::now();
    double diff_time = std::chrono::duration<double, std::milli>(current_time - start_time).count();

    std::cout << "Run time: " << diff_time / 1000. << " sec." << std::endl;
    std::cout << "Total audio processed: " << recognize_client.TotalAudioProcessed() << " sec."
              << std::endl;
    std::cout << "Throughput: " << recognize_client.TotalAudioProcessed() * 1000. / diff_time
              << " RTFX" << std::endl;
    std::cout << "Final transcripts written to " << FLAGS_output_filename << std::endl;
  }

  return 0;
}
