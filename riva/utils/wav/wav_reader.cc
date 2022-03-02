/*
 * SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: MIT
 */


#include "wav_reader.h"

#include <dirent.h>
#include <glog/logging.h>
#include <sys/stat.h>

#include <fstream>
#include <iostream>
#include <sstream>

#include "rapidjson/document.h"
#include "riva/proto/riva_asr.pb.h"

namespace nr = nvidia::riva;
namespace nr_asr = nvidia::riva::asr;

inline std::string
GetFileExt(const std::string& s)
{
  size_t i = s.rfind('.', s.length());
  if (i != std::string::npos) {
    return (s.substr(i + 1, s.length() - i));
  }
  return ("");
}

bool
ParseHeader(std::string file, nr::AudioEncoding& encoding, int& samplerate, int& channels)
{
  std::ifstream file_stream(file);
  FixedWAVHeader header;
  std::streamsize bytes_read =
      file_stream.rdbuf()->sgetn(reinterpret_cast<char*>(&header), sizeof(header));
  if (bytes_read != sizeof(header)) {
    std::cerr << "Error reading file " << file << std::flush << std::endl;
    return false;
  }

  std::string tag(header.chunk_id, 4);
  if (tag == "RIFF") {
    if (header.audioformat == WaveFormat::kPCM)
      encoding = nr::LINEAR_PCM;
    else if (header.audioformat == WaveFormat::kMULAW)
      encoding = nr::MULAW;
    else if (header.audioformat == WaveFormat::kALAW)
      encoding = nr::ALAW;
    else
      return false;
    samplerate = header.samplerate;
    channels = header.numchannels;
    return true;
  } else if (tag == "fLaC") {
    // TODO parse sample rate and channels from stream
    encoding = nr::FLAC;
    samplerate = 16000;
    channels = 1;
    return true;
  }

  return false;
}


bool
IsDirectory(const char* path)
{
  struct stat s;

  stat(path, &s);
  if (s.st_mode & S_IFDIR)
    return true;
  else
    return false;
}

bool
ParseJson(const char* path, std::vector<std::string>& filelist)
{
  std::ifstream manifest_file;
  manifest_file.open(path, std::ifstream::in);

  if (!manifest_file.is_open()) {
    std::cout << "Could not open manifest file" << path << std::endl;
    return false;
  }

  std::string filepath_name("audio_filepath");

  std::string line;
  while (std::getline(manifest_file, line)) {
    rapidjson::Document doc;

    doc.Parse(line.c_str());

    if (!doc.IsObject()) {
      std::cout << "Problem parsing line: " << line << std::endl;
    }

    if (!doc.HasMember(filepath_name.c_str())) {
      std::cout << "Line: " << line << " does not contain " << filepath_name << " key" << std::endl;
      continue;
    }
    std::string filepath = doc[filepath_name.c_str()].GetString();
    filelist.push_back(filepath);
  }

  manifest_file.close();

  return true;
}

void
ParsePath(const char* path, std::vector<std::string>& filelist)
{
  DIR* dir;
  struct dirent* ent;
  char real_path[PATH_MAX];

  if (realpath(path, real_path) == NULL) {
    std::cerr << "invalid path: " << path << std::endl;
    return;
  }

  if (!IsDirectory(real_path)) {
    filelist.push_back(real_path);
    return;
  }

  if ((dir = opendir(real_path)) != NULL) {
    /* print all the files and directories within directory */
    while ((ent = readdir(dir)) != NULL) {
      if (!strcmp(ent->d_name, ".") || !strcmp(ent->d_name, ".."))
        continue;
      std::string full_path = real_path;
      full_path.append("/");
      full_path.append(ent->d_name);
      if (IsDirectory(full_path.c_str()))
        ParsePath(full_path.c_str(), filelist);
      else if (
          full_path.find(".wav") != std::string::npos ||
          full_path.find(".flac") != std::string::npos)
        filelist.push_back(full_path);
    }
    closedir(dir);
  } else {
    /* could not open directory */
    perror("Could not open");
    return;
  }
}

std::string
AudioToString(nr::AudioEncoding& encoding)
// map nr::AudioEncoding to std::string
{
  if (encoding == 0) {
    return "ENCODING_UNSPECIFIED";
  } else if (encoding == 1) {
    return "LINEAR_PCM";
  } else if (encoding == 2) {
    return "FLAC";
  } else if (encoding == 20) {
    return "ALAW";
  } else {
    return "";
  }
}


void
LoadWavData(std::vector<std::shared_ptr<WaveData>>& all_wav, std::string& path)
// pre-loading data
// we don't want to measure I/O
{
  std::cout << "Loading eval dataset..." << std::flush << std::endl;

  std::vector<std::string> filelist;
  std::string file_ext = GetFileExt(path);
  if (file_ext == "json" || file_ext == "JSON") {
    ParseJson(path.c_str(), filelist);
  } else {
    ParsePath(path.c_str(), filelist);
  }

  std::vector<std::pair<uint64_t, std::string>> files_size_name;
  files_size_name.reserve(filelist.size());
  for (auto& filename : filelist) {
    // Get the size
    std::cout << "filename: " << filename << std::endl;
    std::ifstream in(filename, std::ifstream::ate | std::ifstream::binary);
    uint64_t file_size = in.tellg();
    files_size_name.emplace_back(std::make_pair(file_size, filename));
  }


  for (auto& file_size_name : files_size_name) {
    std::string filename = file_size_name.second;

    nr::AudioEncoding encoding;
    int samplerate;
    int channels;
    if (!ParseHeader(filename, encoding, samplerate, channels)) {
      std::cerr << "Invalid file/format";
      return;
    }
    std::shared_ptr<WaveData> wav_data = std::make_shared<WaveData>();

    wav_data->sample_rate = samplerate;
    wav_data->filename = filename;
    wav_data->encoding = encoding;
    wav_data->channels = channels;
    wav_data->data.assign(
        std::istreambuf_iterator<char>(std::ifstream(filename).rdbuf()),
        std::istreambuf_iterator<char>());
    all_wav.push_back(std::move(wav_data));
  }
  std::cout << "Done loading " << files_size_name.size() << " files" << std::endl;
}

int
ParseWavHeader(std::stringstream& wavfile, FixedWAVHeader& header, bool read_header)
{
  if (read_header) {
    bool is_header_valid = false;
    wavfile.read(reinterpret_cast<char*>(&header), sizeof(header));

    if (strncmp(header.format, "WAVE", sizeof(header.format)) == 0) {
      if (header.audioformat == WaveFormat::kPCM && header.bitspersample == 16) {
        is_header_valid = true;
      } else if (
          (header.audioformat == WaveFormat::kMULAW || header.audioformat == WaveFormat::kALAW) &&
          header.bitspersample == 8) {
        is_header_valid = true;
      }
    }

    if (!is_header_valid) {
      LOG(INFO) << "error: unsupported format"
                << " audioformat " << header.audioformat << " channels " << header.numchannels
                << " rate " << header.samplerate << " bitspersample " << header.bitspersample
                << std::endl;
      return -1;
    }

    // Skip to 'data' chunk
    if (strncmp(header.subchunk2ID, "data", sizeof(header.subchunk2ID))) {
      char chunk_id[4];
      while (wavfile.good()) {
        wavfile.read(reinterpret_cast<char*>(&chunk_id), sizeof(chunk_id));
        if (strncmp(chunk_id, "data", sizeof(chunk_id)) == 0) {
          // read size bytes and break
          wavfile.read(reinterpret_cast<char*>(&chunk_id), sizeof(chunk_id));
          break;
        }
        wavfile.seekg(-3, std::ios_base::cur);
      }
    }
  }

  if (wavfile) {
    int wav_size;
    // move to first sample
    // wavfile.seekg(4, std::ios_base::cur);

    // calculate size of samples
    std::streampos curr_pos = wavfile.tellg();
    wavfile.seekg(0, wavfile.end);
    wav_size = wavfile.tellg() - curr_pos;
    wavfile.seekg(curr_pos);

    return wav_size;
  }

  return -2;
}
