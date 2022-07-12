# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

MAJOR = 0
MINOR = 0
PATCH = 2
PRE_RELEASE = 'rc0'

# Use the following formatting: (major, minor, patch, pre-release)
VERSION = (MAJOR, MINOR, PATCH)

__shortversion__ = '.'.join(map(str, VERSION[:3]))
__version__ = '.'.join(map(str, VERSION[:3])) + ''.join(VERSION[3:])

__package_name__ = "riva-api"

__description__ = "Deprecated Python implementation of the Riva Client API"
__keywords__ = 'deep learning, machine learning, gpu, NLP, ASR, TTS, nvidia, speech, language, Riva, client'
