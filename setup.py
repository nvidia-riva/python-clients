# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

import pathlib
import re
import shutil
from glob import glob

import grpc_tools.protoc
import setuptools
from setuptools.command.build_py import build_py


setup_py_dir = pathlib.Path(__file__).parent.absolute()

long_description = ""

CHANGE_PB2_LOC_PATTERN = re.compile('from riva.proto import (.+_pb2.*)')


class BuildPyCommand(build_py):
    def run(self):
        if not self.dry_run:
            target_dir = setup_py_dir / 'riva_api' / 'proto'
            for elem in target_dir.iterdir():
                if elem.name != '__init__.py':
                    if elem.is_dir():
                        shutil.rmtree(str(elem))
                    else:
                        elem.unlink()
            print("glob dir: ", str(setup_py_dir / 'common/riva/proto/*.proto'))
            for proto in glob(str(setup_py_dir / 'common/riva/proto/*.proto')):
                print(proto)
                grpc_tools.protoc.main(
                    [
                        'grpc_tools.protoc',
                        '-I=' + str(setup_py_dir / 'common'),
                        '--python_out=' + str(target_dir),
                        '--grpc_python_out=' + str(target_dir),
                        proto,
                    ]
                )
            for fn in glob(str(target_dir / 'riva' / 'proto' / '*_pb2*.py')):
                with open(fn) as f:
                    text = f.read()
                with open(fn, 'w') as f:
                    f.write(CHANGE_PB2_LOC_PATTERN.sub(r'from . import \1', text))
            # Move Python files to src/riva_api
            for f in glob(str(target_dir / 'riva' / 'proto' / '*.py')):
                shutil.move(f, target_dir)
            # Remove leftover empty dirs
            shutil.rmtree(target_dir / 'riva' / 'proto')
            shutil.rmtree(target_dir / 'riva')
            open(target_dir / '__init__.py', 'w').close()
            super(BuildPyCommand, self).run()


def get_version():
    version_file = setup_py_dir / "VERSION"
    versions = open(version_file, "r").readlines()
    version = "devel"
    for v in versions:
        if v.startswith("RIVA_VERSION: "):
            version = v[len("RIVA_VERSION: ") :].strip()
    return version


setuptools.setup(
    name="riva-api",
    version=get_version(),
    author="apeganov",
    author_email="apeganov@nvidia.com",
    description="Python implementation of the Riva API",
    long_description=long_description,
    url="https://github.com/nvidia-riva/python-clients",
    packages=setuptools.find_packages(),
    cmdclass={"build_py": BuildPyCommand},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
    ],
    python_requires='>=3.6',
    install_requires=['grpcio-tools'],
    setup_requires=['grpcio-tools'],
    exclude=['tests', 'tutorials'],
)
