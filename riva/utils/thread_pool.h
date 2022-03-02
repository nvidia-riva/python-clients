/*
 * SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: MIT
 *
 * Copyright (c) 2012 Jakob Progsch, Václav Zeman
 *
 * This software is provided 'as-is', without any express or implied
 * warranty. In no event will the authors be held liable for any damages
 * arising from the use of this software.
 *
 * Permission is granted to anyone to use this software for any purpose,
 * including commercial applications, and to alter it and redistribute it
 * freely, subject to the following restrictions:
 *
 *   1. The origin of this software must not be misrepresented; you must not
 *   claim that you wrote the original software. If you use this software
 *   in a product, an acknowledgment in the product documentation would be
 *   appreciated but is not required.
 *
 *   2. Altered source versions must be plainly marked as such, and must not be
 *   misrepresented as being the original software.
 *
 *   3. This notice may not be removed or altered from any source
 *   distribution.
 */

#pragma once

#define WAIT_TIME_US 10000

#include <unistd.h>

#include <condition_variable>
#include <functional>
#include <future>
#include <memory>
#include <mutex>
#include <queue>
#include <stdexcept>
#include <thread>
#include <vector>

class ThreadPool {
 public:
  explicit ThreadPool(size_t);

  template <class F, class... Args>
  decltype(auto) Enqueue(F&& f, Args&&... args);

  ~ThreadPool()
  {
    {
      std::lock_guard<std::mutex> lock(queue_mutex_);
      stop_ = true;
    }
    cv_.notify_all();
    for (std::thread& worker : threads_) worker.join();
  }

  void Wait();

 private:
  std::vector<std::thread> threads_;
  std::queue<std::function<void()> > tasks_;

  // synchronization
  std::mutex queue_mutex_;
  std::condition_variable cv_;
  bool stop_;
  std::atomic<int> outstanding_tasks_;
};

// the constructor just launches some amount of workers
inline ThreadPool::ThreadPool(size_t threads = std::thread::hardware_concurrency())
    : stop_(false), outstanding_tasks_(0)
{
  if (!threads) {
    throw std::invalid_argument("at least one thread required");
  }
  threads_.reserve(threads);
  for (size_t i = 0; i < threads; ++i)
    threads_.emplace_back([this] {
      for (;;) {
        std::function<void()> task;
        {
          std::unique_lock<std::mutex> lock(this->queue_mutex_);
          this->cv_.wait(lock, [this] { return this->stop_ || !this->tasks_.empty(); });
          if (this->stop_ && this->tasks_.empty())
            return;
          task = std::move(this->tasks_.front());
          this->tasks_.pop();
        }

        task();
        outstanding_tasks_--;
      }
    });
}

// add new work item to the pool
template <class F, class... Args>
decltype(auto)
ThreadPool::Enqueue(F&& f, Args&&... args)
{
  using return_type = decltype(f(args...));

  auto task = std::make_shared<std::packaged_task<return_type()> >(
      std::bind(std::forward<F>(f), std::forward<Args>(args)...));

  std::future<return_type> res = task->get_future();
  {
    std::lock_guard<std::mutex> lock(queue_mutex_);

    if (stop_) {
      throw std::runtime_error("Enqueue on stopped ThreadPool");
    }

    outstanding_tasks_++;
    tasks_.emplace([task]() { (*task)(); });
  }
  cv_.notify_one();
  return res;
}

inline void
ThreadPool::Wait()
{
  while (outstanding_tasks_ > 0) {
    usleep(WAIT_TIME_US);
  }
}
