# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT

import argparse
import asyncio
import signal
import sys

from riva.client.realtime import RealtimeASRClient
from riva.client.argparse_utils import add_realtime_config_argparse_parameters


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Realtime transcription client that connects to a Riva AI ASR WebSocket server. This script supports two input modes: "
        "microphone input for live transcription or audio file input for offline processing. When using microphone input, "
        "you can specify a recording duration. The script connects to a WebSocket server and streams audio data in real-time, "
        "receiving transcription results as they become available. Results are saved to output files for both audio and text.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    
    parser.add_argument(
        "--input",
        required=True,
        help="Input audio file",
    )
    parser.add_argument("--mic", action="store_true", help="Use microphone input", default=False)
    parser.add_argument(
        "--duration", type=int, help="Recording duration in seconds (for microphone)"
    )
    parser.add_argument(
        "--sample-rate-hz",
        type=int,
        help="A number of frames per second in audio streamed from a microphone.",
        default=16000,
    )
    parser.add_argument(
        "--file-streaming-chunk",
        type=int,
        default=1600,
        help="A maximum number of frames in a audio chunk sent to server.",
    )
    parser.add_argument(
        "--output-text",
        type=str,
        help="Output text file",
    )
    parser = add_realtime_config_argparse_parameters(parser)
    args = parser.parse_args()
    return args


async def main() -> None:
    args = parse_args()
    client = RealtimeASRClient(args.server, args.endpoint, args.query_params, args.sample_rate_hz, args.file_streaming_chunk)       

    # Set up signal handler for graceful shutdown
    def signal_handler(sig, frame):
        print("Interrupt received, stopping...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    try:
        await client.connect()

        if args.mic:
            audio_chunks = client.get_mic_chunks(duration=args.duration)
        else:
            audio_chunks = client.get_audio_chunks(args.input)

        send_task = asyncio.create_task(client.send_audio_chunks(audio_chunks))
        receive_task = asyncio.create_task(client.receive_responses())
        await asyncio.gather(send_task, receive_task)
        
        if args.output_text:
            client.save_responses(args.output_text)

    except Exception as e:
        print(f"Error: {e}")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
