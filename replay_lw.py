#!/usr/bin/env python
"""Replay an episode of the ``local/lw`` dataset on the SO101 follower arm.

Usage (from the ``solo`` venv)::

    python replay_lw.py                     # episode 0, auto-detect follower port
    python replay_lw.py --episode 2         # another episode
    python replay_lw.py --port /dev/ttyACM1 # explicit port
    python replay_lw.py --dry-run           # load and print the actions, no robot

The dataset lives next to this script in ``lw/`` (a copy of
``~/.cache/huggingface/lerobot/local/lw``).
"""

from __future__ import annotations

import argparse
import glob
import sys
import time
from pathlib import Path

DATASET_DIR = Path(__file__).resolve().parent / "lw"
REPO_ID = "local/lw"
DEFAULT_ROBOT_ID = "so101_follower"
FOLLOWER_MIN_VOLTAGE = 8.0  # leader arms run ~5V, follower arms ~12V


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--episode", type=int, default=0, help="episode index to replay (default: 0)")
    parser.add_argument("--port", default="auto", help="follower serial port, or 'auto' to detect by motor voltage")
    parser.add_argument("--robot-id", default=DEFAULT_ROBOT_ID, help="calibration id of the follower arm")
    parser.add_argument("--fps", type=int, default=None, help="override the dataset fps")
    parser.add_argument("--dataset-dir", type=Path, default=DATASET_DIR, help="path to the lw dataset directory")
    parser.add_argument("--dry-run", action="store_true", help="load the episode and print it without touching the robot")
    return parser.parse_args()


def find_follower_port() -> str:
    """Return the serial port whose motor bus reads follower-level voltage."""
    import scservo_sdk as scs

    for port in sorted(glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*")):
        handler = scs.PortHandler(port)
        if not handler.openPort():
            continue
        handler.setBaudRate(1_000_000)
        try:
            raw, result, _ = scs.PacketHandler(0).read1ByteTxRx(handler, 1, 62)  # Present_Voltage of motor 1
        finally:
            handler.closePort()
        if result == scs.COMM_SUCCESS and raw / 10.0 >= FOLLOWER_MIN_VOLTAGE:
            return port
    sys.exit("No follower arm found. Plug it in or pass --port explicitly.")


def load_episode(dataset_dir: Path, episode: int):
    """Return (dataset, list of per-frame action dicts) for one episode."""
    from lerobot.datasets.lerobot_dataset import LeRobotDataset
    from lerobot.utils.constants import ACTION

    if not (dataset_dir / "meta" / "info.json").exists():
        sys.exit(f"Dataset not found at {dataset_dir}")

    dataset = LeRobotDataset(REPO_ID, root=dataset_dir, episodes=[episode])
    if episode >= dataset.meta.total_episodes:
        sys.exit(f"Episode {episode} does not exist; dataset has {dataset.meta.total_episodes} episodes.")

    frames = dataset.hf_dataset.filter(lambda row: row["episode_index"] == episode)
    names = dataset.features[ACTION]["names"]
    actions = [dict(zip(names, row[ACTION].tolist())) for row in frames.select_columns(ACTION)]
    return dataset, actions


def replay(actions: list[dict], fps: int, port: str, robot_id: str) -> None:
    from lerobot.processor import make_default_robot_action_processor
    from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig
    from lerobot.utils.robot_utils import precise_sleep

    robot = SO101Follower(SO101FollowerConfig(port=port, id=robot_id))
    process_action = make_default_robot_action_processor()
    period = 1.0 / fps

    robot.connect()
    try:
        print(f"Replaying {len(actions)} frames at {fps} fps on {port}. Ctrl+C to stop.")
        for action in actions:
            tick = time.perf_counter()
            robot.send_action(process_action((action, robot.get_observation())))
            precise_sleep(max(period - (time.perf_counter() - tick), 0.0))
    except KeyboardInterrupt:
        print("\nStopped by user.")
    finally:
        robot.disconnect()


def main() -> None:
    args = parse_args()
    dataset, actions = load_episode(args.dataset_dir, args.episode)
    fps = args.fps or dataset.fps
    print(f"Loaded episode {args.episode}: {len(actions)} frames, {fps} fps")

    if args.dry_run:
        for i in (0, len(actions) // 2, len(actions) - 1):
            print(f"  frame {i:4d}: " + ", ".join(f"{k}={v:7.2f}" for k, v in actions[i].items()))
        return

    port = find_follower_port() if args.port == "auto" else args.port
    replay(actions, fps, port, args.robot_id)


if __name__ == "__main__":
    main()
