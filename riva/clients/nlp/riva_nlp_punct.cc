/*
 * SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: MIT
 */

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
#include "riva/utils/stamping.h"
#include "riva_nlp_client.h"

using grpc::Status;
using grpc::StatusCode;
namespace nr = nvidia::riva;
namespace nr_nlp = nvidia::riva::nlp;

DEFINE_string(riva_uri, "localhost:50051", "URI to access riva-server");
DEFINE_string(model_name, "riva_punctuation", "Model name to test");
DEFINE_string(queries, "", "Path to a file with one input sentence per line");
DEFINE_string(output, "", "Path to output file");
DEFINE_int32(num_iterations, 1, "Number of times to loop over strings");
DEFINE_int32(parallel_requests, 10, "Number of in-flight requests to send");
DEFINE_bool(print_results, true, "Print final classification results");
DEFINE_bool(use_ssl, false, "Boolean to control if SSL/TLS encryption should be used.");
DEFINE_string(ssl_cert, "", "Path to SSL client certificatates file");


class Query {
 public:
  Query(uint32_t corr_id) : corr_id_(corr_id) {}
  uint32_t GetCorrId() const { return corr_id_; }

 private:
  uint32_t corr_id_;
};

class PunctQuery : public Query {
 public:
  PunctQuery(const std::string& text, const std::string& model, uint32_t _corr_id)
      : Query(_corr_id), text_(text), model_(model)
  {
  }
  std::string GetText() { return text_; }
  std::string GetModel() { return model_; }

 private:
  std::string text_;
  std::string model_;
};

bool
LoadStringData(std::vector<std::string>& all_queries, std::string& path)
{
  std::ifstream in(path.c_str());

  if (!in) {
    std::cerr << "Cannot open path: " << path << std::endl;
    return false;
  }

  std::string str;
  while (std::getline(in, str)) {
    if (str.size() > 0)
      all_queries.push_back(str);
  }
  in.close();
  return true;
}

int
main(int argc, char** argv)
{
  google::InitGoogleLogging(argv[0]);
  FLAGS_logtostderr = 1;

  std::stringstream str_usage;
  str_usage << "Usage: riva_nlp_punct" << std::endl;
  str_usage << "           --queries=<filename> " << std::endl;
  str_usage << "           --riva_uri=<server_name:port> " << std::endl;
  str_usage << "           --num_iterations=<integer> " << std::endl;
  str_usage << "           --parallel_requests=<integer> " << std::endl;
  str_usage << "           --print_results=<true|false> " << std::endl;
  str_usage << "           --output=<filename> " << std::endl;
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

  std::ofstream outfile;
  if (!FLAGS_output.empty()) {
    if (FLAGS_parallel_requests > 1) {
      // Not allowed, we cannot guarantee order of writes to file
      std::cout << "parallel_requests must be 1 when writing outputs to a file." << std::endl;
      return 1;
    } else {
      outfile.open(FLAGS_output);
    }
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

  auto stub = nr_nlp::RivaLanguageUnderstanding::NewStub(grpc_channel);

  auto prepare_func = [&stub](
      grpc::ClientContext * context, const nr_nlp::TextTransformRequest& request,
      grpc::CompletionQueue* cq) -> auto
  {
    return std::move(stub->PrepareAsyncPunctuateText(context, request, cq));
  };

  auto fill_request_func = [](PunctQuery& query, nr_nlp::TextTransformRequest& request) -> void {
    request.add_text(query.GetText());
    request.set_top_n(1);
    auto model = request.mutable_model();
    model->set_model_name(query.GetModel());
    return;
  };

  auto print_response_func =
      [&outfile](PunctQuery& query, nr_nlp::TextTransformResponse& response) -> void {
    // print just the first item in the batch
    std::cout << query.GetCorrId() << ":\t";
    std::cout << "Punct text: " << response.text(0) << std::endl;
    if (!FLAGS_output.empty()) {
      outfile << query.GetCorrId() << "\t" << response.text(0) << std::endl;
    }
    return;
  };

  NLPClient<PunctQuery, nr_nlp::TextTransformResponse, nr_nlp::TextTransformRequest> client(
      prepare_func, fill_request_func, print_response_func, FLAGS_print_results);

  std::vector<std::string> all_queries;
  auto ok = LoadStringData(all_queries, FLAGS_queries);
  if (!ok) {
    return 1;
  }

  uint32_t all_query_max = all_queries.size() * FLAGS_num_iterations;
  std::vector<std::string> all_queries_repeated;
  all_queries_repeated.reserve(all_query_max);
  for (uint32_t file_id = 0; file_id < all_queries.size(); file_id++) {
    for (int iter = 0; iter < FLAGS_num_iterations; iter++) {
      all_queries_repeated.push_back(all_queries[file_id]);
    }
  }

  // Spawn reader thread that loops indefinitely
  std::thread thread_ = std::thread(
      &NLPClient<PunctQuery, nr_nlp::TextTransformResponse, nr_nlp::TextTransformRequest>::
          AsyncCompleteRpc,
      &client);

  // Ensure there's also num_channels requests in flight
  uint32_t all_query_i = 0;
  auto start_time = std::chrono::steady_clock::now();
  while (true) {
    while (client.NumActiveTasks() < (uint32_t)FLAGS_parallel_requests &&
           all_query_i < all_query_max) {
      std::unique_ptr<PunctQuery> query(
          new PunctQuery(all_queries_repeated[all_query_i], FLAGS_model_name, all_query_i));
      client.Infer(std::move(query));
      ++all_query_i;
    }

    if (all_query_i == all_query_max) {
      break;
    }
  }

  client.DoneSending();
  thread_.join();

  if (!FLAGS_output.empty()) {
    outfile.close();
    std::cout << "Output written to " << FLAGS_output << std::endl;
  }

  if (client.NumFailedRequests()) {
    std::cout << "Some requests failed to complete properly, not printing performance stats"
              << std::endl;
  } else {
    auto current_time = std::chrono::steady_clock::now();
    double diff_time = std::chrono::duration<double, std::milli>(current_time - start_time).count();
    std::cout << "Run time: " << diff_time / 1000. << "s" << std::endl;
    std::cout << "Total sequences processed: " << client.TotalSequencesProcessed() << std::endl;
    std::cout << "Throughput: " << client.TotalSequencesProcessed() * 1000. / diff_time
              << " seq/sec" << std::endl;

    client.PrintStats();
  }


  return 0;
}
