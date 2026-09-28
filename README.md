# replay-lw

Standalone replay of the `local/lw` dataset (3 episodes, 598 frames each, 30 fps) on an
SO101 follower arm, using [LeRobot](https://github.com/huggingface/lerobot).
The dataset is bundled in `lw/`.

```
replay_lw.py   replay one episode on the follower arm
find_ports.py  tell which serial port is the leader and which is the follower
lw/            the dataset (LeRobot v3.0 format, parquet only, no videos)
```

## Quick start (arm already calibrated)

```bash
python replay_lw.py --dry-run        # load the data, print sample frames, no robot needed
python replay_lw.py                  # replay episode 0, auto-detect the follower port
python replay_lw.py --episode 2      # episodes 0-2 are available
python replay_lw.py --port /dev/ttyACM1 --robot-id so101_follower --fps 15
```

If you have never calibrated the arm on this machine, follow the setup below first.

---

## Setup and calibration guide

This section is written so that a person **or an AI coding agent** can run it top to bottom.
Each step has a command, what to expect, and a check. Run the steps in order.

> **Note for agents:** steps 5 and 6 are interactive. They ask the human to physically move the
> arm and press Enter. Run those commands in a terminal the human can see and type into, tell
> the human what the on-screen prompt asks for, and wait. Do not try to automate the key presses.

### 1. Install

Python 3.10 to 3.12. Use a fresh virtual environment.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install "lerobot[feetech]==0.4.5" pandas pyarrow
```

Check:

```bash
lerobot-calibrate --help | head -3      # prints usage
python -c "import scservo_sdk"          # prints nothing
```

### 2. Plug in and find the arms

Plug the follower arm (and the leader, if you have one) into USB and power them on.
The follower's power supply is 12 V, the leader's is 5 V.

```bash
python find_ports.py
```

Expected output, one line per arm:

```
/dev/ttyACM0: leader    5.1 V  motors [1, 2, 3, 4, 5, 6]
/dev/ttyACM1: follower 11.8 V  motors [1, 2, 3, 4, 5, 6]
```

Checks:

- Every arm must list **6 motors**. If one is missing (for example `motors [1, 2, 3, 4, 5]`),
  the chain is broken after the last listed motor. Reseat the cable between that motor and the
  next one, then rerun. Do not continue until all 6 answer.
- If the output is empty or says permission denied, see Troubleshooting.
- Port numbers can change after a reboot or replug. Rerun this step whenever in doubt.
  Scripts can get the answer with `python find_ports.py --json`.

Write down the follower port. The rest of this guide calls it `$FOLLOWER_PORT`:

```bash
export FOLLOWER_PORT=/dev/ttyACM1   # replace with the port shown above
export LEADER_PORT=/dev/ttyACM0     # only if you have a leader arm
```

### 3. Choose an arm id

The id is just a name for the calibration file. This repo defaults to `so101_follower`
for the follower and `so101_leader` for the leader. Keep those unless you have a reason not to.

### 4. (Only if motors are misnumbered) Assign motor ids

Skip this if step 2 showed motors 1 to 6 on the arm. Otherwise LeRobot can assign ids one
motor at a time. It asks you to connect a single motor, press Enter, and repeat for each joint.

```bash
lerobot-setup-motors --robot.type=so101_follower --robot.port=$FOLLOWER_PORT
```

Rerun `python find_ports.py` afterwards and confirm 6 motors.

### 5. Calibrate the follower (interactive)

```bash
lerobot-calibrate --robot.type=so101_follower --robot.port=$FOLLOWER_PORT --robot.id=so101_follower
```

What happens on screen, in order:

1. If a calibration file already exists for this id, it asks: press Enter to keep it, or
   type `c` and Enter to recalibrate. Type `c` for a fresh calibration.
2. It disables motor torque so the arm can be moved by hand, then prints
   `Move ... to the MIDDLE of its range of motion` with a live table of joint positions.
   Move every joint to roughly the middle of its travel. Rows turn green when they are close
   enough. When all rows are green it says `Press ENTER to continue`. Press Enter.
3. It prints `Move all joints except 'wrist_roll' sequentially through their entire ranges of
   motion. Recording positions. Press ENTER to stop`. Slowly move each joint, including the
   gripper, all the way to both ends of its travel. Then press Enter.
4. It prints `Calibration saved to <path>` and exits.

Check that the file exists and has 6 entries:

```bash
python -c "import json,pathlib; p=pathlib.Path.home()/'.cache/huggingface/lerobot/calibration/robots/so101_follower/so101_follower.json'; d=json.load(open(p)); print(p); print(list(d))"
```

Expected:

```
['shoulder_pan', 'shoulder_lift', 'elbow_flex', 'wrist_flex', 'wrist_roll', 'gripper']
```

### 6. Calibrate the leader (optional, only for teleoperation)

Same flow as step 5 with the teleoperator flags:

```bash
lerobot-calibrate --teleop.type=so101_leader --teleop.port=$LEADER_PORT --teleop.id=so101_leader
```

The file lands in `~/.cache/huggingface/lerobot/calibration/teleoperators/so101_leader/so101_leader.json`.

### 7. Verify with a dry run, then a real replay

```bash
python replay_lw.py --dry-run
```

Expected: `Loaded episode 0: 598 frames, 30 fps` followed by three sample frames. No robot is touched.

Now clear the space around the follower arm and run the real thing:

```bash
python replay_lw.py --port $FOLLOWER_PORT --robot-id so101_follower
```

Expected: `Replaying 598 frames at 30 fps on /dev/ttyACM1. Ctrl+C to stop.` and the arm moves
for about 20 seconds, then torque is released and the script exits. Ctrl+C stops it early.

### Where things live

| What | Path |
|---|---|
| Follower calibration | `~/.cache/huggingface/lerobot/calibration/robots/so101_follower/<id>.json` |
| Leader calibration | `~/.cache/huggingface/lerobot/calibration/teleoperators/so101_leader/<id>.json` |
| Dataset used by this repo | `./lw/` |
| Same dataset in the LeRobot cache | `~/.cache/huggingface/lerobot/local/lw/` |

To use a different calibration file, pass its id with `--robot-id`. To use another copy of
the dataset, pass `--dataset-dir`.

## Troubleshooting

**`Missing motor IDs: - 6`** on connect. One motor is not answering on the bus. Run
`python find_ports.py`, find which id is missing, and reseat the cable between the previous
motor and it. The gripper (id 6) is last in the chain and the most common one to drop out.

**`Permission denied: '/dev/ttyACM0'`** (Linux). Add yourself to the `dialout` group and log
out and back in:

```bash
sudo usermod -aG dialout $USER
```

**`No follower arm found`** from `replay_lw.py`. Auto-detection reads the bus voltage from
motor 1. If your follower runs below 8 V, pass `--port` explicitly.

**Ports swapped after a reboot.** Rerun `python find_ports.py`. Nothing in this repo depends
on a fixed port number.

**Robot type in the dataset says `so_follower`.** That is the internal name LeRobot 0.4.x
gives to SO100/SO101 followers. It matches `--robot.type=so101_follower`.
