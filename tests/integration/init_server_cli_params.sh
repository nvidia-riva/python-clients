# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

if [ -z "${SERVER}" ]; then
  server_args="--server localhost:50051"
else
  server_args="--server ${SERVER}"
fi
if [ ! -z "${USE_SSL}" ] && [ "${USE_SSL}" != 0 ]; then
  server_args="${server_args} --use-ssl"
fi
if [ ! -z "${SSL_CERT}" ]; then
  server_args="${server_args} --ssl-cert ${SSL_CERT}"
fi