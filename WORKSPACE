workspace(name = "com_nvidia_riva_api")
load("@bazel_tools//tools/build_defs/repo:http.bzl", "http_archive")

# alsa is only library required to exist in local environment
new_local_repository(
    name = "alsa",
    path = "/usr/lib/x86_64-linux-gnu",
    build_file = "third_party/BUILD.alsa"
)

http_archive(
  name = "com_google_absl",
  urls = ["https://github.com/abseil/abseil-cpp/archive/c22c032a353b5dc16d86ddc879e628344e591e77.zip"],
  strip_prefix = "abseil-cpp-c22c032a353b5dc16d86ddc879e628344e591e77",
  sha256 = "88e79f5b7e3f92d3f19ad470cb38ef6becaf9bf195206ca9dba1a23d4017bc1a"
)

http_archive(
    name = "com_github_grpc_grpc",
    sha256 = "8c05641b9f91cbc92f51cc4a5b3a226788d7a63f20af4ca7aaca50d92cc94a0d",
    strip_prefix = "grpc-1.44.0",
    urls = [
        "https://github.com/grpc/grpc/archive/v1.44.0.tar.gz",
    ],
)

http_archive(
    name = "com_github_gflags_gflags",
    strip_prefix = "gflags-2.2.2",
    sha256 = "34af2f15cf7367513b352bdcd2493ab14ce43692d2dcd9dfc499492966c64dcf",
    urls = [
        "https://github.com/gflags/gflags/archive/v2.2.2.tar.gz",
    ],
)

http_archive(
    name = "glog",
    urls = ["https://github.com/google/glog/archive/v0.4.0.tar.gz"],
    sha256 = "f28359aeba12f30d73d9e4711ef356dc842886968112162bc73002645139c39c",
    strip_prefix = "glog-0.4.0",
)

http_archive(
    name = "googletest",
    url = "https://github.com/google/googletest/archive/refs/tags/release-1.11.0.tar.gz",
    sha256 = "b4870bf121ff7795ba20d20bcdd8627b8e088f2d1dab299a031c1034eddc93d5",
    strip_prefix = "googletest-release-1.11.0",
)

http_archive(
    name = "rapidjson",
    urls = ["https://github.com/Tencent/rapidjson/archive/0ccdbf364c577803e2a751f5aededce935314313.zip"],
    sha256 = "79c7e037e25413673e29676e579676d761380329427d221ff74a4c00bf82efac",
    strip_prefix = "rapidjson-0ccdbf364c577803e2a751f5aededce935314313",
    build_file = "@//third_party:BUILD.rapidjson"
)

load("@com_github_grpc_grpc//bazel:grpc_deps.bzl", "grpc_deps")
grpc_deps()
load("@com_github_grpc_grpc//bazel:grpc_extra_deps.bzl", "grpc_extra_deps")
grpc_extra_deps()
