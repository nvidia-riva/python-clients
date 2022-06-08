# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

import importlib
import os
import pathlib
import re
import shutil
import subprocess as sp
from glob import glob

import grpc_tools.protoc
import setuptools
from setuptools.command.build_py import build_py


spec = importlib.util.spec_from_file_location('package_info', 'riva_api/package_info.py')
package_info = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package_info)


__contact_emails__ = package_info.__contact_emails__
__contact_names__ = package_info.__contact_names__
__description__ = package_info.__description__
__download_url__ = package_info.__download_url__
__homepage__ = package_info.__homepage__
__keywords__ = package_info.__keywords__
__license__ = package_info.__license__
__package_name__ = package_info.__package_name__
__repository_url__ = package_info.__repository_url__
__version__ = package_info.__version__


setup_py_dir = pathlib.Path(__file__).parent.absolute()

with open("README.md", "r", encoding='utf-8') as fh:
    long_description = fh.read()
long_description_content_type = "text/markdown"

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
            cwd = os.getcwd()
            os.chdir(str(setup_py_dir))
            common_dir = setup_py_dir / 'common'
            if common_dir.exists():
                if common_dir.is_dir():
                    shutil.rmtree(str(common_dir))
                else:
                    raise ValueError(f"Found unexpected file {common_dir} in repo root. It should be a directory.")
            subprocess_args = ['git', 'clone', 'https://github.com/nvidia-riva/common.git', str(common_dir)]
            completed_git_clone = sp.run(subprocess_args)
            if completed_git_clone.returncode > 0:
                raise RuntimeError(f"Could not properly finish cloning of common repo")
            # subprocess_args = ['git', 'submodule', 'update', '--init']
            # completed_git_submodule_process = sp.run(subprocess_args)
            # if completed_git_submodule_process.returncode > 0:
            #     raise RuntimeError(
            #         f"Could not properly finish `{' '.join(subprocess_args)}' command."
            #         f"Return code: {completed_git_submodule_process.returncode}"
            #     )
            os.chdir(cwd)
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
    name=__package_name__,
    license=__license__,
    version=__version__,
    author=__contact_names__,
    author_email=__contact_emails__,
    description=__description__,
    long_description=long_description,
    long_description_content_type=long_description_content_type,
    url=__repository_url__,
    maintainer=__contact_names__,
    maintainer_email=__contact_emails__,
    keywords=__keywords__,
    packages=setuptools.find_packages(exclude=['tests', 'tutorials', 'scripts']),
    cmdclass={"build_py": BuildPyCommand},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
    ],
    python_requires='>=3.6',
    install_requires=['grpcio-tools'],
    setup_requires=['grpcio-tools'],
)
