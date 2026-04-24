"""Regression tests for services.ollama — double-start guard, chat stream cleanup.

Guards:
- H-01 double-start: ``start()`` is a no-op when our instance is already running
  (serialized under ``_start_lock``). Prior behaviour killed our own port holder
  and relaunched; the guard prevents that self-kill cycle.
- H-02 manager atomicity: pins ``start_process`` check+Popen inside ``_lock``.
- H-07 chat streaming: the generator returned by ``chat(..., stream=True)``
  closes the underlying ``requests.Response`` when abandoned early.
"""

import threading
import types
import pytest


# ─── H-01 Ollama double-start guard ───────────────────────────────────────────

def test_start_noop_when_already_running(monkeypatch):
    """start() short-circuits when is_running()+check_port() both true."""
    from services import ollama

    # Pretend the binary is installed.
    monkeypatch.setattr(ollama, 'is_installed', lambda: True)
    # Pretend our tracked instance is alive on the port.
    monkeypatch.setattr(ollama, 'is_running', lambda sid: True)
    monkeypatch.setattr(ollama, 'check_port', lambda port: True)

    # Point get_db at a stub row with a registered pid.
    class _Row(dict):
        def __getitem__(self, key):
            return super().__getitem__(key)

    class _Cur:
        def __init__(self, row):
            self._row = row
        def fetchone(self):
            return self._row

    class _DB:
        def execute(self, *_args, **_kw):
            return _Cur(_Row(pid=12345))
        def close(self):
            self.closed = True

    monkeypatch.setattr(ollama, 'get_db', lambda: _DB())

    # These would be called if start() did NOT short-circuit. Fail loud if so.
    def _boom(*_a, **_kw):
        raise AssertionError('start() did not short-circuit — kill/relaunch path taken')
    monkeypatch.setattr(ollama, '_kill_port_holder', _boom)
    monkeypatch.setattr(ollama, 'start_process', _boom)

    pid = ollama.start()
    assert pid == 12345, 'should return the registered PID when already running'


def test_start_lock_serializes_concurrent_callers(monkeypatch):
    """Two threads calling start() concurrently do not both enter the kill-path.

    The slow path reclaims the port + launches. With two racers and a running
    instance the second must observe the first's state (is_running=True) and
    short-circuit — not race ahead and kill the live process.
    """
    from services import ollama

    state = {'started': False, 'kills': 0, 'pid': 99999}

    monkeypatch.setattr(ollama, 'is_installed', lambda: True)

    def _is_running(sid):
        return state['started']

    def _check_port(port):
        return state['started']

    class _Row(dict):
        def __getitem__(self, key):
            return super().__getitem__(key)

    class _Cur:
        def fetchone(self):
            return _Row(pid=state['pid']) if state['started'] else None

    class _DB:
        def execute(self, *_a, **_kw):
            return _Cur()
        def close(self):
            pass

    def _kill(port):
        state['kills'] += 1

    def _start_process(*_a, **_kw):
        import time
        time.sleep(0.05)   # simulate launch latency so racer can land mid-window
        state['started'] = True
        return state['pid']

    monkeypatch.setattr(ollama, 'is_running', _is_running)
    monkeypatch.setattr(ollama, 'check_port', _check_port)
    monkeypatch.setattr(ollama, 'get_db', lambda: _DB())
    monkeypatch.setattr(ollama, '_kill_port_holder', _kill)
    monkeypatch.setattr(ollama, 'start_process', _start_process)
    monkeypatch.setattr(ollama, 'get_models_dir', lambda: '/tmp/nomad_test_models')
    # Bypass platform/config imports that start() performs inline.
    import sys
    fake_platform = types.SimpleNamespace(
        get_ollama_gpu_env=lambda: {},
        find_pid_on_port=lambda p: None,
    )
    monkeypatch.setitem(sys.modules, 'platform_utils', fake_platform)
    fake_config = types.SimpleNamespace(Config=types.SimpleNamespace(APP_HOST='127.0.0.1'))
    monkeypatch.setitem(sys.modules, 'config', fake_config)
    # Make get_install_dir() cheap.
    monkeypatch.setattr(ollama, 'get_install_dir', lambda: '/tmp/nomad_test_install')
    monkeypatch.setattr(ollama, 'get_exe_path', lambda: '/tmp/nomad_test_install/ollama')
    # Make the post-launch poll return immediately.
    monkeypatch.setattr(ollama.time, 'sleep', lambda _s: None)

    pids = []
    def _runner():
        pids.append(ollama.start())

    threads = [threading.Thread(target=_runner) for _ in range(5)]
    for t in threads: t.start()
    for t in threads: t.join(timeout=5)

    # All callers must receive the same PID. Only one launch can have happened
    # (the others short-circuited under the guard); zero kills of an existing
    # instance because none was there until we started it.
    assert all(p == state['pid'] for p in pids), f'racer PIDs diverged: {pids}'
    assert state['started'] is True, 'at least one thread must have launched'
    assert state['kills'] == 0, 'no kill-path should have fired — we own the port'


# ─── H-02 manager.start_process atomicity ─────────────────────────────────────

def test_manager_start_process_check_and_popen_live_in_same_with_lock_block():
    """The liveness check (``_processes[sid].poll() is None``) and the Popen
    that would replace it must both be descendants of the SAME ``with _lock:``
    ``ast.With`` node inside ``services.manager.start_process``. This pins the
    atomicity invariant so a refactor that opens a second lock block, dedents
    the Popen out of the critical section, or reorders check/launch across
    lock boundaries fails the test — not the contract.
    """
    import ast
    import inspect
    import textwrap
    from services import manager

    src = textwrap.dedent(inspect.getsource(manager.start_process))
    tree = ast.parse(src)
    fn = tree.body[0]
    assert isinstance(fn, ast.FunctionDef) and fn.name == 'start_process'

    def _is_with_lock(node):
        if not isinstance(node, ast.With):
            return False
        for item in node.items:
            expr = item.context_expr
            if isinstance(expr, ast.Name) and expr.id == '_lock':
                return True
        return False

    def _subtree_has_poll_is_none(node):
        for child in ast.walk(node):
            # Match ``<anything>.poll() is None`` — the ``<anything>`` is
            # typically ``_processes[service_id]`` but the invariant is the
            # poll() call being compared against None, not the exact subject.
            if (isinstance(child, ast.Compare)
                    and isinstance(child.left, ast.Call)
                    and isinstance(child.left.func, ast.Attribute)
                    and child.left.func.attr == 'poll'
                    and len(child.ops) == 1
                    and isinstance(child.ops[0], ast.Is)
                    and len(child.comparators) == 1
                    and isinstance(child.comparators[0], ast.Constant)
                    and child.comparators[0].value is None):
                return True
        return False

    def _subtree_has_popen(node):
        for child in ast.walk(node):
            if (isinstance(child, ast.Call)
                    and isinstance(child.func, ast.Attribute)
                    and child.func.attr == 'Popen'
                    and isinstance(child.func.value, ast.Name)
                    and child.func.value.id == 'subprocess'):
                return True
        return False

    with_lock_blocks = [n for n in ast.walk(fn) if _is_with_lock(n)]
    assert with_lock_blocks, 'start_process has no `with _lock:` block — atomicity lost'

    # Find a single ``with _lock:`` block that owns BOTH the poll-is-None
    # check AND the subprocess.Popen call. Any split across two different
    # lock blocks would silently break atomicity (caller B could enter the
    # second block between A's check and A's launch).
    unified = [b for b in with_lock_blocks
               if _subtree_has_poll_is_none(b) and _subtree_has_popen(b)]
    assert unified, (
        'No single `with _lock:` block in start_process contains BOTH the '
        '`<proc>.poll() is None` liveness check and the `subprocess.Popen(...)` '
        'call. The check + launch must be atomic under the same lock.'
    )


# ─── H-07 chat stream abandonment releases the response ──────────────────────

def test_chat_stream_closes_on_early_abandonment(monkeypatch):
    """If the caller starts iterating the streaming generator and then
    abandons it, the underlying response is closed via the finally clause.

    Note: close() on a never-started generator is a no-op in CPython (the
    body never ran, so there's no suspended yield for GeneratorExit to
    unwind into). The real-world concern is a consumer that reads a few
    lines and then bails — that case must release the socket.
    """
    from services import ollama

    closed = {'count': 0}

    class _FakeResp:
        status_code = 200
        def raise_for_status(self):
            pass
        def iter_lines(self):
            yield b'{"message":{"content":"a"},"done":false}'
            yield b'{"message":{"content":"b"},"done":false}'
            yield b'{"message":{"content":"c"},"done":true}'
        def close(self):
            closed['count'] += 1

    monkeypatch.setattr(ollama.requests, 'post', lambda *_a, **_kw: _FakeResp())

    gen = ollama.chat('llama3.2:3b', [{'role': 'user', 'content': 'hi'}], stream=True)
    first = next(gen)  # enter generator body → try block is active
    assert b'"a"' in first
    gen.close()        # GeneratorExit → finally → resp.close()
    assert closed['count'] == 1, 'streaming resp.close() must fire on explicit abandonment'


def test_chat_stream_closes_on_full_iteration(monkeypatch):
    """Generator close also fires when the stream is fully consumed."""
    from services import ollama

    closed = {'count': 0}

    class _FakeResp:
        status_code = 200
        def raise_for_status(self):
            pass
        def iter_lines(self):
            yield b'{"message":{"content":"a"},"done":false}'
            yield b'{"message":{"content":"b"},"done":true}'
        def close(self):
            closed['count'] += 1

    monkeypatch.setattr(ollama.requests, 'post', lambda *_a, **_kw: _FakeResp())

    lines = list(ollama.chat('llama3.2:3b', [{'role': 'user', 'content': 'hi'}], stream=True))
    assert len(lines) == 2
    assert closed['count'] == 1
