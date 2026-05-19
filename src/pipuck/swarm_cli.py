"""CLI for controlling Pi-puck swarms."""

import argparse
import json
import sys
from typing import List

from .swarm import (
    DEFAULT_CONTROL_PORT,
    DEFAULT_DISCOVERY_PORT,
    Swarm,
    SwarmAgent,
    SwarmCommand,
    normalize_plan,
)


def _parse_step(value: str) -> SwarmCommand:
    parts = [p.strip() for p in value.split(",")]
    if len(parts) != 3:
        raise ValueError("Step must be left,right,duration")
    return SwarmCommand(int(parts[0]), int(parts[1]), float(parts[2]))


def _parse_plan(args: argparse.Namespace) -> List[SwarmCommand]:
    steps = []
    if args.plan_file:
        with open(args.plan_file, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        steps.extend(normalize_plan(data))
    if args.plan:
        for chunk in args.plan.split(";"):
            chunk = chunk.strip()
            if chunk:
                steps.append(_parse_step(chunk))
    if args.step:
        for step in args.step:
            steps.append(_parse_step(step))
    if not steps:
        raise ValueError("Plan is required (use --step, --plan, or --plan-file)")
    return normalize_plan(steps)


def _cmd_list(args: argparse.Namespace) -> int:
    swarm = Swarm(
        discovery_port=args.discovery_port,
        control_port=args.control_port,
        broadcast_addr=args.broadcast,
        discovery_timeout=args.timeout,
    )
    members = swarm.discover()
    if not members:
        print("No Pi-pucks discovered.")
        return 1
    for member in members:
        line = "{name:>16}  {addr:>15}:{port}  id={id}".format(
            name=member.name,
            addr=member.address,
            port=member.control_port,
            id=member.agent_id or "-",
        )
        print(line)
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    swarm = Swarm(
        discovery_port=args.discovery_port,
        control_port=args.control_port,
        broadcast_addr=args.broadcast,
        discovery_timeout=args.timeout,
        socket_timeout=args.socket_timeout,
    )
    plan = _parse_plan(args)
    members = swarm.discover()
    if args.targets:
        targets = swarm.resolve_targets(members, args.targets)
    else:
        targets = members
    if not targets:
        print("No targets available.")
        return 1
    results = swarm.send_plan(targets, plan, wait=args.wait, timeout=args.socket_timeout)
    failed = False
    for key, resp in results.items():
        ok = bool(resp.get("ok")) if isinstance(resp, dict) else False
        status = "ok" if ok else "error"
        print("{}:{} -> {}".format(key[0], key[1], status))
        if not ok:
            failed = True
            print("  reason:", resp)
    return 1 if failed else 0


def _cmd_agent(args: argparse.Namespace) -> int:
    agent = SwarmAgent(
        name=args.name,
        agent_id=args.agent_id,
        discovery_port=args.discovery_port,
        control_port=args.control_port,
        bind_address=args.bind,
        i2c_channel=args.i2c_channel,
        i2c_address=args.i2c_address,
    )
    print(
        "Pi-puck swarm agent running: name={} id={} discovery_port={} control_port={}".format(
            agent.name,
            agent.agent_id or "-",
            agent.discovery_port,
            agent.control_port,
        )
    )
    agent.serve_forever()
    return 0


def main(argv: List[str] = None) -> int:
    parser = argparse.ArgumentParser(description="Pi-puck swarm control CLI")
    sub = parser.add_subparsers(dest="command")

    list_p = sub.add_parser("list", help="Discover available Pi-pucks")
    list_p.add_argument("--discovery-port", type=int, default=DEFAULT_DISCOVERY_PORT)
    list_p.add_argument("--control-port", type=int, default=DEFAULT_CONTROL_PORT)
    list_p.add_argument("--broadcast", default="255.255.255.255")
    list_p.add_argument("--timeout", type=float, default=1.0)
    list_p.set_defaults(func=_cmd_list)

    run_p = sub.add_parser("run", help="Send a plan to Pi-pucks")
    run_p.add_argument("--discovery-port", type=int, default=DEFAULT_DISCOVERY_PORT)
    run_p.add_argument("--control-port", type=int, default=DEFAULT_CONTROL_PORT)
    run_p.add_argument("--broadcast", default="255.255.255.255")
    run_p.add_argument("--timeout", type=float, default=1.0)
    run_p.add_argument("--socket-timeout", type=float, default=5.0)
    run_p.add_argument("--targets", nargs="+", help="Target names, IDs, or host[:port]")
    run_p.add_argument("--wait", action="store_true", help="Wait for plan completion")
    run_p.add_argument("--step", action="append", help="Single command: left,right,duration")
    run_p.add_argument("--plan", help="Semicolon-separated steps: l,r,d; l,r,d")
    run_p.add_argument("--plan-file", help="JSON file with plan list")
    run_p.set_defaults(func=_cmd_run)

    agent_p = sub.add_parser("agent", help="Run a Pi-puck swarm agent")
    agent_p.add_argument("--name", help="Agent display name")
    agent_p.add_argument("--agent-id", help="Agent identifier")
    agent_p.add_argument("--discovery-port", type=int, default=DEFAULT_DISCOVERY_PORT)
    agent_p.add_argument("--control-port", type=int, default=DEFAULT_CONTROL_PORT)
    agent_p.add_argument("--bind", default="", help="Bind address (default all)")
    agent_p.add_argument("--i2c-channel", type=int, default=None)
    agent_p.add_argument("--i2c-address", type=int, default=None)
    agent_p.set_defaults(func=_cmd_agent)

    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 1
    try:
        return args.func(args)
    except Exception as exc:
        print("Error:", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
