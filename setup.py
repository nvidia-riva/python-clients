# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

import importlib
import pathlib

import setuptools


spec = importlib.util.spec_from_file_location('package_info', 'riva_api/package_info.py')
package_info = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package_info)


__description__ = package_info.__description__
__keywords__ = package_info.__keywords__
__package_name__ = package_info.__package_name__
__version__ = package_info.__version__


setup_py_dir = pathlib.Path(__file__).parent.absolute()

with open("README.md", "r", encoding='utf-8') as fh:
    long_description = fh.read()
long_description_content_type = "text/markdown"


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
    license='UNKNOWN',
    version=__version__,
    author='UNKNOWN',
    author_email='UNKNOWN',
    description=__description__,
    long_description='''Use `nvidia-riva-client <https://pypi.org/project/nvidia-riva-client/>`_ instead.''',
    long_description_content_type=long_description_content_type,
    url='UNKNOWN',
    maintainer='UNKNOWN',
    maintainer_email='UNKNOWN',
    keywords=__keywords__,
    # packages=setuptools.find_packages(exclude=['tests', 'tutorials', 'scripts']),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
    ],
    python_requires='>=3.6',
    install_requires=['nvidia-riva-client'],
)
