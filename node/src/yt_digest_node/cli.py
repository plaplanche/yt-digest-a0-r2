"""The `yt-digest-node` command (spec 5): `transcript <video_id> [--langs] [--request-id]`."""

import argparse
import dataclasses
import os
import re
import sys
from collections.abc import Mapping, Sequence

from yt_digest_node import __version__
from yt_digest_node.extractors import extractor_from_env
from yt_digest_node.log import emit
from yt_digest_node.pipeline import Config, parse_langs, run

_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
BAD_ARGUMENT = 2


def _video_id(value: str) -> str:
    if not _VIDEO_ID.match(value):
        raise argparse.ArgumentTypeError(f"invalid video id {value!r}")
    return value


def _langs(value: str) -> tuple[str, ...]:
    try:
        return parse_langs(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="yt-digest-node")
    commands = parser.add_subparsers(dest="command", required=True)
    transcript = commands.add_parser("transcript", help="print the transcript result of a video")
    transcript.add_argument("video_id", type=_video_id)
    transcript.add_argument("--langs", type=_langs, help="language order, such as fr,en")
    transcript.add_argument("--request-id")
    return parser


def main(argv: Sequence[str] | None = None, env: Mapping[str, str] | None = None) -> int:
    """Run the command: the result on standard output, logs on standard error; exit 0 whatever
    the status, 2 on a bad argument or configuration, without printing a result."""
    args = _parser().parse_args(argv)
    env = os.environ if env is None else env
    try:
        config = Config.from_env(env)
        if args.langs is not None:
            config = dataclasses.replace(config, langs=args.langs)
        extractor = extractor_from_env(env, config.langs)
    except ValueError as error:
        print(f"yt-digest-node: {error}", file=sys.stderr)
        return BAD_ARGUMENT
    emit("service.started", request_id=args.request_id, attrs={"version": __version__})
    result = run(args.video_id, config, extractor, args.request_id)
    print(result.model_dump_json())
    return 0
