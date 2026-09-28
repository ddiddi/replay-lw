# replay-lw

Standalone replay of the `local/lw` dataset (3 episodes, 598 frames each, 30 fps) on the SO101 follower arm.
The dataset is bundled in `lw/` (copied from `~/.cache/huggingface/lerobot/local/lw`).

```bash
cd ~/Desktop/solo && source .venv/bin/activate
python replay-lw/replay_lw.py --dry-run        # check the data loads, no robot needed
python replay-lw/replay_lw.py                  # replay episode 0, auto-detect follower port
python replay-lw/replay_lw.py --episode 2      # pick an episode (0-2)
python replay-lw/replay_lw.py --port /dev/ttyACM1 --robot-id so101_follower
```

Requires the follower arm to be calibrated under the given `--robot-id` (default `so101_follower`)
and all 6 motors present on the bus.
