"""Swarm discovery and control for Pi-puck devices."""

import json
import socket
import socketserver
import threading
import time
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple, Union


DEFAULT_DISCOVERY_PORT = 64530
DEFAULT_CONTROL_PORT = 64531
PROTOCOL_VERSION = 1
DISCOVERY_MESSAGE = {"type": "discover", "service": "pipuck-swarm", "version": PROTOCOL_VERSION}
ANNOUNCE_TYPE = "announce"
RUN_PLAN_TYPE = "run_plan"


@dataclass(frozen=True)
class SwarmCommand:
    left: int
    right: int
    duration: float

    def to_payload(self) -> dict:
        return {"left": int(self.left), "right": int(self.right), "duration": float(self.duration)}


@dataclass(frozen=True)
class SwarmMember:
    name: str
    address: str
    control_port: int
    agent_id: Optional[str] = None

    def key(self) -> Tuple[str, int]:
        return (self.address, int(self.control_port))

    def matches(self, token: str) -> bool:
        token = token.strip()
        if not token:
            return False
        if token == self.address:
            return True
        if token == self.name:
            return True
        if self.agent_id and token == self.agent_id:
            return True
        return False


def normalize_plan(plan: Sequence[Union[SwarmCommand, Sequence[Union[int, float]], dict]]) -> List[SwarmCommand]:
    if not plan:
        raise ValueError("Plan must contain at least one command")
    steps = []
    for step in plan:
        if isinstance(step, SwarmCommand):
            cmd = step
        elif isinstance(step, dict):
            if "left" not in step or "right" not in step or "duration" not in step:
                raise ValueError("Each plan item must include left, right, and duration")
            cmd = SwarmCommand(int(step["left"]), int(step["right"]), float(step["duration"]))
        elif isinstance(step, (list, tuple)) and len(step) == 3:
            cmd = SwarmCommand(int(step[0]), int(step[1]), float(step[2]))
        else:
            raise ValueError("Unsupported plan entry: {}".format(step))
        if cmd.duration < 0:
            raise ValueError("Command duration must be non-negative")
        steps.append(cmd)
    return steps


def _encode_message(payload: dict) -> bytes:
    return json.dumps(payload).encode("utf-8")


def _decode_message(raw: bytes) -> Optional[dict]:
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


def _read_line(sock: socket.socket, limit: int = 65536) -> Optional[bytes]:
    buf = bytearray()
    while len(buf) < limit:
        chunk = sock.recv(1024)
        if not chunk:
            break
        buf.extend(chunk)
        if b"\n" in chunk:
            break
    if not buf:
        return None
    return bytes(buf.split(b"\n", 1)[0])


def _parse_host_port(token: str, default_port: int) -> Tuple[str, int]:
    token = token.strip()
    if ":" in token:
        host, port = token.rsplit(":", 1)
        return host.strip(), int(port)
    return token, int(default_port)


class Swarm:
    def __init__(
        self,
        discovery_port: int = DEFAULT_DISCOVERY_PORT,
        control_port: int = DEFAULT_CONTROL_PORT,
        broadcast_addr: str = "255.255.255.255",
        discovery_timeout: float = 1.0,
        socket_timeout: float = 2.0,
    ):
        self.discovery_port = int(discovery_port)
        self.control_port = int(control_port)
        self.broadcast_addr = broadcast_addr
        self.discovery_timeout = float(discovery_timeout)
        self.socket_timeout = float(socket_timeout)

    def discover(self, timeout: Optional[float] = None) -> List[SwarmMember]:
        deadline = time.time() + (timeout if timeout is not None else self.discovery_timeout)
        results = {}
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(0.2)
            sock.sendto(_encode_message(DISCOVERY_MESSAGE), (self.broadcast_addr, self.discovery_port))
            while True:
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                sock.settimeout(min(0.2, remaining))
                try:
                    data, addr = sock.recvfrom(4096)
                except socket.timeout:
                    continue
                msg = _decode_message(data)
                if not msg or msg.get("type") != ANNOUNCE_TYPE:
                    continue
                name = str(msg.get("name") or addr[0])
                control_port = int(msg.get("control_port") or self.control_port)
                agent_id = msg.get("id")
                member = SwarmMember(name=name, address=addr[0], control_port=control_port, agent_id=agent_id)
                results[member.key()] = member
        finally:
            sock.close()
        return list(results.values())

    def send_plan(
        self,
        targets: Iterable[Union[SwarmMember, Tuple[str, int], str]],
        plan: Sequence[Union[SwarmCommand, Sequence[Union[int, float]], dict]],
        wait: bool = False,
        timeout: Optional[float] = None,
    ) -> dict:
        steps = normalize_plan(plan)
        payload = {
            "type": RUN_PLAN_TYPE,
            "version": PROTOCOL_VERSION,
            "plan": [step.to_payload() for step in steps],
            "wait": bool(wait),
        }
        results = {}
        for target in targets:
            member = self._coerce_target(target)
            results[member.key()] = self._send_request(member, payload, timeout=timeout)
        return results

    def broadcast_plan(
        self,
        plan: Sequence[Union[SwarmCommand, Sequence[Union[int, float]], dict]],
        wait: bool = False,
        timeout: Optional[float] = None,
    ) -> dict:
        targets = self.discover()
        return self.send_plan(targets, plan, wait=wait, timeout=timeout)

    def resolve_targets(self, members: Sequence[SwarmMember], selectors: Sequence[str]) -> List[SwarmMember]:
        resolved = []
        seen = set()
        for token in selectors:
            match = None
            for member in members:
                if member.matches(token):
                    match = member
                    break
            if match is None:
                host, port = _parse_host_port(token, self.control_port)
                match = SwarmMember(name=host, address=host, control_port=port)
            if match.key() not in seen:
                resolved.append(match)
                seen.add(match.key())
        return resolved

    def _coerce_target(self, target: Union[SwarmMember, Tuple[str, int], str]) -> SwarmMember:
        if isinstance(target, SwarmMember):
            return target
        if isinstance(target, tuple) and len(target) == 2:
            return SwarmMember(name=str(target[0]), address=str(target[0]), control_port=int(target[1]))
        if isinstance(target, str):
            host, port = _parse_host_port(target, self.control_port)
            return SwarmMember(name=host, address=host, control_port=port)
        raise ValueError("Unsupported target: {}".format(target))

    def _send_request(self, member: SwarmMember, payload: dict, timeout: Optional[float] = None) -> dict:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.socket_timeout if timeout is None else float(timeout))
        try:
            sock.connect((member.address, member.control_port))
            sock.sendall(_encode_message(payload) + b"\n")
            raw = _read_line(sock)
            if not raw:
                return {"ok": False, "error": "empty response"}
            msg = _decode_message(raw)
            if not msg:
                return {"ok": False, "error": "invalid response"}
            return msg
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
        finally:
            sock.close()


class SwarmAgent:
    def __init__(
        self,
        name: Optional[str] = None,
        agent_id: Optional[str] = None,
        discovery_port: int = DEFAULT_DISCOVERY_PORT,
        control_port: int = DEFAULT_CONTROL_PORT,
        bind_address: str = "",
        i2c_channel: Optional[int] = None,
        i2c_address: Optional[int] = None,
    ):
        self.name = name or socket.gethostname()
        self.agent_id = agent_id
        self.discovery_port = int(discovery_port)
        self.control_port = int(control_port)
        self.bind_address = bind_address
        self.i2c_channel = i2c_channel
        self.i2c_address = i2c_address
        self._control_server = None
        self._discovery_server = None
        self._plan_lock = threading.Lock()

    def serve_forever(self) -> None:
        self._start_servers()
        try:
            while True:
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        for server in (self._discovery_server, self._control_server):
            if server:
                try:
                    server.shutdown()
                except Exception:
                    pass
                try:
                    server.server_close()
                except Exception:
                    pass

    def _start_servers(self) -> None:
        if self._discovery_server or self._control_server:
            return
        self._discovery_server = _DiscoveryServer((self.bind_address, self.discovery_port), _DiscoveryHandler, self)
        self._control_server = _ControlServer((self.bind_address, self.control_port), _ControlHandler, self)
        threading.Thread(target=self._discovery_server.serve_forever, daemon=True).start()
        threading.Thread(target=self._control_server.serve_forever, daemon=True).start()

    def _announce_payload(self) -> dict:
        return {
            "type": ANNOUNCE_TYPE,
            "service": "pipuck-swarm",
            "version": PROTOCOL_VERSION,
            "name": self.name,
            "id": self.agent_id,
            "control_port": self.control_port,
        }

    def _handle_plan_request(self, payload: dict) -> dict:
        if payload.get("version") not in (None, PROTOCOL_VERSION):
            return {"ok": False, "error": "unsupported version"}
        try:
            plan = normalize_plan(payload.get("plan") or [])
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
        wait = bool(payload.get("wait"))
        acquired = self._plan_lock.acquire(blocking=False)
        if not acquired:
            return {"ok": False, "error": "busy"}
        if wait:
            try:
                self._execute_plan(plan)
            except Exception as exc:
                return {"ok": False, "error": str(exc)}
            finally:
                self._plan_lock.release()
            return {"ok": True}
        thread = threading.Thread(target=self._execute_plan_thread, args=(plan,), daemon=True)
        thread.start()
        return {"ok": True, "status": "started"}

    def _execute_plan_thread(self, plan: List[SwarmCommand]) -> None:
        try:
            self._execute_plan(plan)
        finally:
            self._plan_lock.release()

    def _execute_plan(self, plan: List[SwarmCommand]) -> None:
        from .pipuck import PiPuck

        with PiPuck(i2c_channel=self.i2c_channel, address=self.i2c_address or 0x1F) as pi:
            bot = pi.epuck2
            try:
                for cmd in plan:
                    bot.set_wheel_speeds(cmd.left, cmd.right)
                    bot.update()
                    time.sleep(max(0.0, float(cmd.duration)))
            finally:
                bot.set_wheel_speeds(0, 0)
                bot.update()


class _DiscoveryServer(socketserver.ThreadingUDPServer):
    allow_reuse_address = True

    def __init__(self, server_address, handler_class, agent: SwarmAgent):
        self.agent = agent
        super().__init__(server_address, handler_class)


class _ControlServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, server_address, handler_class, agent: SwarmAgent):
        self.agent = agent
        super().__init__(server_address, handler_class)


class _DiscoveryHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        data = self.request[0]
        sock = self.request[1]
        msg = _decode_message(data)
        if not msg or msg.get("type") != DISCOVERY_MESSAGE["type"]:
            return
        if msg.get("service") != DISCOVERY_MESSAGE["service"]:
            return
        payload = self.server.agent._announce_payload()
        sock.sendto(_encode_message(payload), self.client_address)


class _ControlHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        raw = _read_line(self.request)
        if not raw:
            return
        msg = _decode_message(raw)
        if not msg:
            self.request.sendall(_encode_message({"ok": False, "error": "invalid request"}) + b"\n")
            return
        if msg.get("type") != RUN_PLAN_TYPE:
            self.request.sendall(_encode_message({"ok": False, "error": "unknown command"}) + b"\n")
            return
        response = self.server.agent._handle_plan_request(msg)
        self.request.sendall(_encode_message(response) + b"\n")
