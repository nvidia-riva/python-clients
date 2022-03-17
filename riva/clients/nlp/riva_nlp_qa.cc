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
DEFINE_string(questions, "", "Path to a file with one question per line");
DEFINE_string(contexts, "", "Path to a file with one context per line");
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

class QAQuery : public Query {
 public:
  QAQuery(const std::string& query, const std::string& context, uint32_t _corr_id)
      : Query(_corr_id), qa_context_(context), qa_query_(query)
  {
  }
  std::string GetContext() { return qa_context_; }
  std::string GetQuery() { return qa_query_; }

 private:
  std::string qa_context_;
  std::string qa_query_;
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
  str_usage << "Usage: riva_nlp_qa" << std::endl;
  str_usage << "           --questions=<filename> " << std::endl;
  str_usage << "           --contexts=<filename> " << std::endl;
  str_usage << "           --riva_uri=<server_name:port> " << std::endl;
  str_usage << "           --num_iterations=<integer> " << std::endl;
  str_usage << "           --parallel_requests=<integer> " << std::endl;
  str_usage << "           --print_results=<true|false> " << std::endl;
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
      grpc::ClientContext * context, const nr_nlp::NaturalQueryRequest& request,
      grpc::CompletionQueue* cq) -> auto
  {
    return std::move(stub->PrepareAsyncNaturalQuery(context, request, cq));
  };

  auto fill_request_func = [](QAQuery& query, nr_nlp::NaturalQueryRequest& request) -> void {
    request.set_context(query.GetContext());
    request.set_query(query.GetQuery());
    return;
  };

  auto print_response_func = [](QAQuery& query, nr_nlp::NaturalQueryResponse& response) -> void {
    // print just the first item in the batch
    std::cout << query.GetCorrId() << ":\t";
    std::cout << "Answer: " << response.results(0).answer() << std::endl;
    std::cout << "Score: " << response.results(0).score() << std::endl;
    return;
  };

  NLPClient<QAQuery, nr_nlp::NaturalQueryResponse, nr_nlp::NaturalQueryRequest> client(
      prepare_func, fill_request_func, print_response_func, FLAGS_print_results);

  std::vector<std::string> all_questions;
  auto ok = LoadStringData(all_questions, FLAGS_questions);
  if (!ok) {
    return 1;
  }

  std::vector<std::string> all_contexts;
  ok = LoadStringData(all_contexts, FLAGS_contexts);
  if (!ok) {
    return 1;
  }

  if (all_questions.size() != all_contexts.size()) {
    std::cout << "Number of questions is different than number of contexts" << std::endl;
    return 1;
  }

  uint32_t all_query_max = all_questions.size() * FLAGS_num_iterations;
  std::vector<std::pair<std::string, std::string>> all_queries_repeated;
  all_queries_repeated.reserve(all_query_max);
  for (uint32_t file_id = 0; file_id < all_questions.size(); file_id++) {
    for (int iter = 0; iter < FLAGS_num_iterations; iter++) {
      all_queries_repeated.push_back(std::make_pair(all_questions[file_id], all_contexts[file_id]));
    }
  }

  // Spawn reader thread that loops indefinitely
  std::thread thread_ = std::thread(
      &NLPClient<
          QAQuery, nr_nlp::NaturalQueryResponse, nr_nlp::NaturalQueryRequest>::AsyncCompleteRpc,
      &client);

  // Ensure there's also num_channels requests in flight
  uint32_t all_query_i = 0;
  auto start_time = std::chrono::steady_clock::now();
  while (true) {
    while (client.NumActiveTasks() < (uint32_t)FLAGS_parallel_requests &&
           all_query_i < all_query_max) {
      std::unique_ptr<QAQuery> query(new QAQuery(
          all_queries_repeated[all_query_i].first, all_queries_repeated[all_query_i].second,
          all_query_i));
      client.Infer(std::move(query));
      ++all_query_i;
    }

    if (all_query_i == all_query_max) {
      break;
    }
  }

  client.DoneSending();
  thread_.join();

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
