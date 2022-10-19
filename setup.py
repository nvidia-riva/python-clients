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


spec = importlib.util.spec_from_file_location('package_info', 'riva/client/package_info.py')
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
            target_dir = setup_py_dir / 'riva/client/proto'
            for elem in target_dir.iterdir():
                if elem.name != '__init__.py':
                    if elem.is_dir():
                        shutil.rmtree(str(elem))
                    else:
                        elem.unlink()
            cwd = os.getcwd()
            os.chdir(str(setup_py_dir))

            # # A code which makes sdist distributions installable by `pip`
            #
            # common_dir = setup_py_dir / 'common'
            # if common_dir.exists():
            #     if common_dir.is_dir():
            #         shutil.rmtree(str(common_dir))
            #     else:
            #         raise ValueError(f"Found unexpected file {common_dir} in repo root. It should be a directory.")
            # subprocess_args = ['git', 'clone', 'https://github.com/nvidia-riva/common.git', str(common_dir)]
            # completed_git_clone = sp.run(subprocess_args)
            # if completed_git_clone.returncode > 0:
            #     raise RuntimeError(f"Could not properly finish cloning of common repo")

            # # A code which may be improved in future to replace a commented block above.
            # # `git submodule` commands are preferable compared to `git clone`.
            #
            # subprocess_args = ['git', 'submodule', 'update', '--init']
            # completed_git_submodule_process = sp.run(subprocess_args)
            # if completed_git_submodule_process.returncode > 0:
            #     raise RuntimeError(
            #         f"Could not properly finish `{' '.join(subprocess_args)}' command."
            #         f"Return code: {completed_git_submodule_process.returncode}"
            #     )

            os.chdir(cwd)
            glob_dir = str(setup_py_dir / 'common/riva/proto/*.proto')
            print("glob dir: ", glob_dir)
            protos = glob(glob_dir)
            if not protos:
                raise ValueError(
                    f"No proto files matching glob {glob_dir} were found. If {setup_py_dir / 'common'} directory is "
                    f"empty, you may try to fix it by calling `git submodule update --init`. If you unintentionally "
                    f"removed {setup_py_dir / 'common'} content, then you may try `cd {setup_py_dir / 'common'} && "
                    f"git stash && cd -`."
                )
            for proto in glob(glob_dir):
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
            for fn in glob(str(target_dir / 'riva/proto/*_pb2*.py')):
                with open(fn) as f:
                    text = f.read()
                with open(fn, 'w') as f:
                    f.write(CHANGE_PB2_LOC_PATTERN.sub(r'from . import \1', text))
            # Move Python files to riva/client
            for f in glob(str(target_dir / 'riva/proto/*.py')):
                shutil.move(f, target_dir)
            # Remove leftover empty dirs
            shutil.rmtree(target_dir / 'riva/proto')
            shutil.rmtree(target_dir / 'riva')
            open(target_dir / '__init__.py', 'w').close()
            super(BuildPyCommand, self).run()


def req_file(filename):
    with open(filename, encoding='utf-8') as f:
        content = f.readlines()
    # you may also want to remove whitespace characters
    # Example: `\n` at the end of each line
    return [x.strip() for x in content]


install_requires = req_file("requirements.txt")


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
    # packages=setuptools.find_packages(exclude=['tests', 'tutorials', 'scripts']),
    package_dir={"riva.client": "riva/client"},
    cmdclass={"build_py": BuildPyCommand},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
    ],
    python_requires='>=3.7',
    install_requires=install_requires,
    setup_requires=['grpcio-tools'],
)
