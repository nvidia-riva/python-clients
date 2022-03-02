#!/bin/bash

# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

set -e -o pipefail

# The upstream git URL
git_url=$(git config --get remote.origin.url)
echo "GIT_URL ${git_url}"

# The git commit checksum, with "-dirty" if modified
git_sha=$(git describe --tags --match XXXXXXX --always --abbrev=40 --dirty)
echo "GIT_SHA ${git_sha}"

# Tag name, or GIT_SHA if not on a tag
git_ref=$(git describe --tags --no-match --always --abbrev=40 --dirty | sed -E 's/^.*-g([0-9a-f]{40}-?.*)$/\1/')
echo "GIT_REF ${git_ref}"

# Plain git revision for linkstamping.
# echo "BUILD_SCM_REVISION" $(git rev-parse HEAD)
echo "BUILD_SCM_REVISION" ${git_ref}

# Git tree status for linkstamping.
if [[ -n $(git status --porcelain) ]];
then
    tree_status="Modified"
else
    tree_status="Clean"
fi
echo "BUILD_SCM_STATUS ${tree_status}"
