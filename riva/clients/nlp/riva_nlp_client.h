/*
 * SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: MIT
 */

#pragma once

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

#include "riva/proto/riva_nlp.grpc.pb.h"

using grpc::Status;
using grpc::StatusCode;

namespace nr = nvidia::riva;
namespace nr_nlp = nvidia::riva::nlp;

template <class T_Query, class T_Response, class T_Request>
class NLPClient {
 public:
  using PrepareFunc = std::function<std::unique_ptr<::grpc::ClientAsyncResponseReader<T_Response>>(
      ::grpc::ClientContext*, const T_Request&, ::grpc::CompletionQueue*)>;

  using FillRequestFunc = std::function<void(T_Query& query, T_Request& request)>;

  using PrintResponseFunc = std::function<void(T_Query& query, T_Response& response)>;

  NLPClient(
      PrepareFunc prepare_func, FillRequestFunc fill_request_func,
      PrintResponseFunc print_response_func, bool print_results)
      : prepare_func_(prepare_func), fill_request_func_(fill_request_func),
        print_response_func_(print_response_func), print_results_(print_results),
        total_sequences_processed_(0), done_sending_(false), num_requests_(0), num_responses_(0),
        num_failed_requests_(0)
  {
  }

  uint32_t NumActiveTasks()
  {
    std::lock_guard<std::mutex> lock(mutex_);
    return curr_tasks_.size();
  }

  size_t TotalSequencesProcessed() { return total_sequences_processed_; }

  uint32_t NumFailedRequests() { return num_failed_requests_; }

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

    std::cout << std::setprecision(3);
    std::cout << "Latencies:\tMedian\t\t90\t\t95\t\t99\t\tAvg\n";
    std::cout << "\t\t" << median << "\t\t" << lat_90 << "\t\t" << lat_95 << "\t\t" << lat_99
              << "\t\t" << avg << std::endl;
  }

  void DoneSending()
  {
    done_sending_ = true;
    std::cout << "Done sending " << num_requests_ << " requests" << std::endl;
    return;
  }

  // Assembles the client's payload and sends it to the server.
  void Infer(std::unique_ptr<T_Query> query)
  {
    // Data we are sending to the server.
    T_Request request;
    fill_request_func_(*query, request);

    {
      std::lock_guard<std::mutex> lock(mutex_);
      curr_tasks_.emplace(query->GetCorrId());
      num_requests_++;
    }

    // Call object to store rpc data
    AsyncClientCall* call = new AsyncClientCall;

    call->query = std::move(query);
    call->start_time = std::chrono::steady_clock::now();

    // stub_->PrepareAsyncSayHello() creates an RPC object, returning
    // an instance to store in "call" but does not actually start the RPC
    // Because we are using the asynchronous API, we need to hold on to
    // the "call" instance in order to get updates on the ongoing RPC.
    call->response_reader = prepare_func_(&call->context, request, &cq_);

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
        total_sequences_processed_++;
        latencies_.push_back(lat);

        if (print_results_) {
          std::lock_guard<std::mutex> lock(mutex_);
          print_response_func_(*(call->query), call->response);
        }
      } else {
        std::cout << "RPC failed. Code: " << call->status.error_code() << std::endl;
        std::cout << "  Message: " << call->status.error_message() << std::endl;
        std::cout << "  Details: " << call->status.error_details() << std::endl;
        num_failed_requests_++;
      }

      // Remove the element from the map
      {
        std::lock_guard<std::mutex> lock(mutex_);
        curr_tasks_.erase(call->query->GetCorrId());
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
    T_Response response;

    // Context for the client. It could be used to convey extra information to
    // the server and/or tweak certain RPC behaviors.
    grpc::ClientContext context;

    // Storage for the status of the RPC upon completion.
    grpc::Status status;

    std::unique_ptr<grpc::ClientAsyncResponseReader<T_Response>> response_reader;

    std::unique_ptr<T_Query> query;
    std::chrono::time_point<std::chrono::steady_clock> start_time;
  };

  // The producer-consumer queue we use to communicate asynchronously with the
  // gRPC runtime.
  grpc::CompletionQueue cq_;

  std::set<uint32_t> curr_tasks_;

  PrepareFunc prepare_func_;
  FillRequestFunc fill_request_func_;
  PrintResponseFunc print_response_func_;
  bool print_results_;

  size_t total_sequences_processed_;
  std::vector<double> latencies_;

  std::mutex mutex_;
  bool done_sending_;
  uint32_t num_requests_;
  uint32_t num_responses_;
  uint32_t num_failed_requests_;
};
