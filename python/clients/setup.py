import os
import pathlib

import pkg_resources
import setuptools
from setuptools import Command
from setuptools.command.build_py import build_py

setup_py_dir = pathlib.Path(__file__).parent.absolute()

# with open("README.md", "r") as f:
#     long_description = f.read()
long_description = ""


class BuildPyCommand(build_py):
    def run(self):
        if not self.dry_run:
            import grpc_tools.protoc
            from glob import glob
            from pathlib import Path
            import os, subprocess, shutil

            target_dir = os.path.join(str(setup_py_dir), '..', '..', 'riva', 'riva_api')
            try:
                os.mkdir(target_dir)
            except:
                print('riva_api directory exists, rewriting files')
            print("glob dir: ", str(setup_py_dir) + '/../../common/riva/proto/*.proto')
            for proto in glob(str(setup_py_dir) + '/../../common/riva/proto/*.proto'):
                print(proto)
                grpc_tools.protoc.main(
                    [
                        'grpc_tools.protoc',
                        '-I=' + str(setup_py_dir) + '/../../',
                        '--python_out=' + target_dir,
                        '--grpc_python_out=' + target_dir,
                        proto,
                    ]
                )
            subprocess.check_output(
                [
                    "sed -i -r 's/from riva.proto import (.+_pb2.*)/from . import \\1/g' riva/riva_api/riva/proto/*_pb2*.py"
                ],
                shell=True,
            )
            # Move Python files to src/riva_api
            for f in glob(os.path.join(target_dir, 'riva', 'proto', '*.py')):
                shutil.move(f, target_dir)
            # Remove leftover empty dirs
            os.rmdir(os.path.join(target_dir, 'riva', 'proto'))
            os.rmdir(os.path.join(target_dir, 'riva'))
            super(BuildPyCommand, self).run()


def get_version():
    version_file = setup_py_dir / ".." / ".." / "VERSION"
    versions = open(version_file, "r").readlines()
    version = "devel"
    for v in versions:
        if v.startswith("RIVA_VERSION: "):
            version = v[len("RIVA_VERSION: ") :].strip()
    return version


setuptools.setup(
    name="riva-api",
    version=get_version(),
    author="NVIDIA",
    author_email="nvidia.com",
    description="Python implementation of the Riva API",
    long_description=long_description,
    url="nvidia.com",
    package_dir={'': 'riva'},
    packages=["riva_api"],
    cmdclass={"build_py": BuildPyCommand},
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
    ],
    python_requires='>=3.6',
    install_requires=['grpcio-tools'],
    setup_requires=['grpcio-tools'],
)
