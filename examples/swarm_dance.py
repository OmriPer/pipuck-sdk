"""Simple swarm "dance" example: discover peers and broadcast a dance plan.

This script discovers nearby Pi-puck agents and broadcasts a short sequence
of wheel commands so the entire swarm performs synchronized "dance" moves.

Usage: run on a machine with network access to Pi-puck agents:
  python3 examples/swarm_dance.py

You can adjust repetition with `--repeat N`.
You can also specify explicit target IPs if UDP broadcast discovery is blocked:
  python3 examples/swarm_dance.py --targets 192.168.1.32,192.168.1.34
"""

import sys
import time
from typing import List

from pipuck import Swarm, SwarmCommand


DEFAULT_REPEAT = 1


def build_dance_plan(speed: int = 300, return_to_start: bool = True) -> List[SwarmCommand]:
    """Return a list of SwarmCommand making a short dance sequence.

    If `return_to_start` is True the function will append the time-reversed,
    inverted commands to bring the robot back to its starting pose.
    """
    s = int(speed)
    # Core dance: forward, spin left, forward, spin right
    body: List[SwarmCommand] = [
        SwarmCommand(s, s, 0.8),          # forward
        SwarmCommand(-s, s, 0.6),         # spin left
        SwarmCommand(s, s, 0.8),          # forward
        SwarmCommand(s, -s, 0.6),         # spin right
    ]

    # Wiggle: alternate small turns
    for _ in range(3):
        body.append(SwarmCommand(int(0.6 * s), int(-0.6 * s), 0.25))
        body.append(SwarmCommand(int(-0.6 * s), int(0.6 * s), 0.25))

    # Final forward before reversing
    body.append(SwarmCommand(s, s, 0.6))

    if return_to_start:
        # Build reversed/inverted sequence to undo the body commands.
        reversed_body = [SwarmCommand(-cmd.left, -cmd.right, cmd.duration) for cmd in reversed(body)]
        plan = body + reversed_body
    else:
        plan = body

    # Short stop to ensure motors brake
    plan.append(SwarmCommand(0, 0, 0.1))
    return plan


def main(argv: List[str]) -> int:
    repeat = DEFAULT_REPEAT
    speed = 300
    targets = None
    # Simple CLI parsing
    i = 1
    while i < len(argv):
        if argv[i] == "--repeat" and i + 1 < len(argv):
            try:
                repeat = int(argv[i + 1])
            except Exception:
                pass
            i += 2
        elif argv[i] == "--speed" and i + 1 < len(argv):
            try:
                speed = int(argv[i + 1])
            except Exception:
                pass
            i += 2
        elif argv[i] == "--targets" and i + 1 < len(argv):
            targets = [t.strip() for t in argv[i + 1].split(",") if t.strip()]
            i += 2
        else:
            print(__doc__)
            return 2

    swarm = Swarm()
    if targets:
        print("Using specified targets: {}".format(targets))
        members = swarm.resolve_targets([], targets)
    else:
        print("Discovering Pi-puck agents on the network...")
        members = swarm.discover()
        if not members:
            print("No agents found. Ensure devices are on and reachable.")
            return 1

    print("Found {} agent(s):".format(len(members)))
    for m in members:
        print(" - {} @ {}:{}".format(m.name, m.address, m.control_port))

    plan = build_dance_plan(speed=speed)

    plan_duration = sum(cmd.duration for cmd in plan)

    try:
        for r in range(max(1, repeat)):
            print("Broadcasting dance plan (round {}/{})...".format(r + 1, repeat))
            results = swarm.send_plan(members, plan, wait=False)
            # Print simple per-target status
            ok_count = sum(1 for v in results.values() if v.get("ok"))
            print(" -> started on {}/{} agents".format(ok_count, len(results)))
            # Wait for the plan to complete before starting the next round
            time.sleep(plan_duration + 0.4)
    except KeyboardInterrupt:
        print("Interrupted, exiting.")
        return 130

    print("Dance complete. Stopping motors on agents as a safeguard...")
    # Broadcast a stop command to ensure motors are zeroed
    swarm.send_plan(members, [SwarmCommand(0, 0, 0.05)], wait=False)

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

