#!/usr/bin/env python3
"""Example: Send goCharge skill to Pi-puck robots to autonomously find and dock with charging station.

The goCharge skill uses proximity sensors to:
1. Detect the charging dock nearby
2. Navigate toward it
3. Align with the dock entrance
4. Slowly approach and connect for charging
"""

import argparse
from pipuck import Swarm


def main():
    parser = argparse.ArgumentParser(description="Send goCharge skill to Pi-pucks")
    parser.add_argument("--targets", nargs="+", help="Target names/IDs/addresses (default: all discovered)")
    parser.add_argument("--wait", action="store_true", help="Wait for charging to complete")
    parser.add_argument("--timeout", type=float, default=30.0, help="Socket timeout in seconds")
    parser.add_argument("--max-iterations", type=int, default=100, help="Max navigation iterations")
    parser.add_argument("--proximity-threshold", type=int, default=2000, help="Sensor threshold to detect dock")
    parser.add_argument("--alignment-threshold", type=int, default=300, help="Sensor balance for alignment")
    parser.add_argument("--approach-speed", type=int, default=200, help="Motor speed during approach")
    parser.add_argument("--dock-timeout", type=float, default=10.0, help="Max time to find dock (seconds)")
    args = parser.parse_args()
    
    # Create swarm controller
    swarm = Swarm(socket_timeout=args.timeout)

    if args.targets:
        targets = swarm.resolve_targets([], args.targets)
    else:
        # Discover available devices only when no explicit targets are provided.
        print("Discovering Pi-pucks...")
        members = swarm.discover()
        if not members:
            print("No Pi-pucks discovered.")
            return 1

        print(f"Found {len(members)} device(s):")
        for m in members:
            print(f"  - {m.name} ({m.address}:{m.control_port})")
        targets = members
    
    if not targets:
        print("No targets selected.")
        return 1
    
    print(f"\nSending goCharge to {len(targets)} target(s)...")
    
    # Build skill parameters
    parameters = {
        "max_iterations": args.max_iterations,
        "proximity_threshold": args.proximity_threshold,
        "alignment_threshold": args.alignment_threshold,
        "approach_speed": args.approach_speed,
        "dock_timeout": args.dock_timeout,
    }
    
    # Send skill
    results = swarm.send_skill(
        targets,
        "goCharge",
        parameters=parameters,
        wait=args.wait,
        timeout=args.timeout
    )
    
    # Report results
    all_ok = True
    for key, resp in results.items():
        ok = bool(resp.get("ok")) if isinstance(resp, dict) else False
        status = "✓" if ok else "✗"
        print(f"{status} {key[0]}:{key[1]} -> {resp}")
        if not ok:
            all_ok = False
    
    if args.wait and all_ok:
        print("\nAll devices successfully charged!")
    elif args.wait and not all_ok:
        print("\nSome devices encountered errors during charging.")
    else:
        print("\nSkill commands sent (async execution).")
    
    return 0 if all_ok else 1


if __name__ == "__main__":
    exit(main())
