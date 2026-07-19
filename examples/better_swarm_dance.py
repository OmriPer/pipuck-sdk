"""Advanced swarm "dance" example: discover peers and broadcast an organic dance plan.

This script generates a randomized, organic-looking sequence of movements. 
Because the sequence is generated once on the controller and sent to all agents,
the entire swarm executes the exact same "random" moves in perfect synchronization,
giving a highly coordinated but natural swarming effect.

Usage:
  python3 examples/better_swarm_dance.py [--targets IP,...] [--repeat N] [--speed S] [--moves M]
"""

import random
import sys
import time
from typing import List

from pipuck import Swarm, SwarmCommand

DEFAULT_REPEAT = 1

def build_swarmy_dance(moves_count: int = 6, base_speed: int = 300, return_to_start: bool = True) -> List[SwarmCommand]:
    """Generate a sequence of swarmy, organic commands."""
    plan: List[SwarmCommand] = []
    
    # Generate random but smooth-looking actions
    for _ in range(moves_count):
        move_type = random.choice(["swoop", "surge", "wiggle", "pivot", "arc_back"])
        
        if move_type == "swoop":
            # Smooth arc
            bias = random.uniform(0.2, 0.7)
            speed = random.randint(int(base_speed * 0.7), int(base_speed * 1.2))
            dur = random.uniform(0.5, 1.5)
            if random.choice([True, False]):
                plan.append(SwarmCommand(speed, int(speed * bias), dur))
            else:
                plan.append(SwarmCommand(int(speed * bias), speed, dur))
                
        elif move_type == "surge":
            # Quick straight movement
            speed = random.randint(base_speed, int(base_speed * 1.5))
            plan.append(SwarmCommand(speed, speed, random.uniform(0.3, 0.8)))
            
        elif move_type == "wiggle":
            # Rapid alternating turns (like a happy tail wag)
            speed = int(base_speed * 0.8)
            for _ in range(random.randint(2, 4)):
                plan.append(SwarmCommand(speed, -speed, 0.15))
                plan.append(SwarmCommand(-speed, speed, 0.15))
                
        elif move_type == "pivot":
            # Spin in place
            speed = int(base_speed * 0.6)
            dur = random.uniform(0.4, 0.8)
            if random.choice([True, False]):
                plan.append(SwarmCommand(speed, -speed, dur))
            else:
                plan.append(SwarmCommand(-speed, speed, dur))
                
        elif move_type == "arc_back":
            # Backward sweeping curve
            speed = -random.randint(int(base_speed * 0.6), base_speed)
            bias = random.uniform(0.3, 0.8)
            dur = random.uniform(0.6, 1.2)
            if random.choice([True, False]):
                plan.append(SwarmCommand(speed, int(speed * bias), dur))
            else:
                plan.append(SwarmCommand(int(speed * bias), speed, dur))
                
    if return_to_start:
        # Build reversed sequence to undo the commands and return near start
        reversed_plan = [SwarmCommand(-cmd.left, -cmd.right, cmd.duration) for cmd in reversed(plan)]
        plan.extend(reversed_plan)
        
    # Short stop
    plan.append(SwarmCommand(0, 0, 0.1))
    
    return plan

def main(argv: List[str]) -> int:
    repeat = DEFAULT_REPEAT
    speed = 300
    targets = None
    moves = 6
    
    i = 1
    while i < len(argv):
        if argv[i] == "--repeat" and i + 1 < len(argv):
            try: repeat = int(argv[i + 1])
            except: pass
            i += 2
        elif argv[i] == "--speed" and i + 1 < len(argv):
            try: speed = int(argv[i + 1])
            except: pass
            i += 2
        elif argv[i] == "--moves" and i + 1 < len(argv):
            try: moves = int(argv[i + 1])
            except: pass
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

    # Generate a random dance plan that all members will share
    plan = build_swarmy_dance(moves_count=moves, base_speed=speed)
    plan_duration = sum(cmd.duration for cmd in plan)

    try:
        for r in range(max(1, repeat)):
            print("Broadcasting organic dance plan (round {}/{})...".format(r + 1, repeat))
            results = swarm.send_plan(members, plan, wait=False)
            ok_count = sum(1 for v in results.values() if v.get("ok"))
            print(" -> started on {}/{} agents. Sequence duration: {:.1f}s".format(ok_count, len(results), plan_duration))
            time.sleep(plan_duration + 0.4)
    except KeyboardInterrupt:
        print("Interrupted, exiting.")
        return 130

    print("Dance complete. Stopping motors on agents...")
    swarm.send_plan(members, [SwarmCommand(0, 0, 0.05)], wait=False)
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))
