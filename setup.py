import pathlib
import shutil
import subprocess
from glob import glob

import grpc_tools.protoc
import setuptools
from setuptools.command.build_py import build_py


setup_py_dir = pathlib.Path(__file__).parent.absolute()

long_description = ""


class BuildPyCommand(build_py):
    def run(self):
        if not self.dry_run:
            target_dir = setup_py_dir / 'riva' / 'riva_api'
            target_dir.mkdir(parents=True, exist_ok=True)
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
            subprocess.check_output(
                [
                    "sed -i -r 's/from riva.proto import (.+_pb2.*)/from . import \\1/g' riva/riva_api/riva/proto/*_pb2*.py"
                ],
                shell=True,
            )
            # Move Python files to src/riva_api
            for f in glob(str(target_dir / 'riva' / 'proto' / '*.py')):
                shutil.move(f, target_dir)
            # Remove leftover empty dirs
            shutil.rmtree(target_dir / 'riva' / 'proto')
            shutil.rmtree(target_dir / 'riva')
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
