"""Lua source obfuscation with a portable, randomized runtime decoder."""

import os
import secrets
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

from antlr4 import InputStream, Token
from luaparser import ast
from luaparser.parser.LuaLexer import LuaLexer


STRENGTH_LEVELS = {"light": 0, "medium": 128, "strong": 32}
_PROMETHEUS = Path(__file__).resolve().parent / "vendor" / "prometheus"
_ROBLOX_INPUT_LIMIT = 64 * 1024
_ROBLOX_OUTPUT_LIMIT = 16 * 1024 * 1024
_ROBLOX_TIMEOUT = 30
_ROBLOX_WORKERS = threading.BoundedSemaphore(2)


def _obfuscate_roblox(source: str) -> str:
    """Run the vendored VM compiler for its supported subset of Luau."""
    if len(source.encode("utf-8")) > _ROBLOX_INPUT_LIMIT:
        raise ValueError("Roblox mode accepts scripts up to 64 KiB")
    lua = shutil.which("lua5.1")
    openssl = shutil.which("openssl")
    if not lua or not openssl:
        raise RuntimeError(
            "Roblox mode requires Lua 5.1 and OpenSSL on the server. "
            "Deploy using the repository Dockerfile, or install both tools and add them to PATH."
        )
    if not _ROBLOX_WORKERS.acquire(blocking=False):
        raise RuntimeError("Roblox obfuscation is busy; please try again")
    try:
        return _run_roblox_compiler(source, lua, openssl)
    finally:
        _ROBLOX_WORKERS.release()


def _run_roblox_compiler(source: str, lua: str, openssl: str) -> str:
    with tempfile.TemporaryDirectory(prefix="nebula-luau-") as directory:
        source_path = Path(directory) / "input.luau"
        output_path = Path(directory) / "output.luau"
        source_path.write_text(source, encoding="utf-8")
        try:
            result = subprocess.run(
                [lua, str(_PROMETHEUS / "cli.lua"), "--nocolors", "--LuaU",
                 "--preset", "Xien", "--out", str(output_path), str(source_path)],
                cwd=_PROMETHEUS,
                env={"PATH": os.path.dirname(openssl) + os.pathsep + os.defpath},
                capture_output=True, text=True, timeout=_ROBLOX_TIMEOUT,
                errors="replace",
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Roblox obfuscation exceeded its time limit") from exc
        except OSError as exc:
            raise RuntimeError("Could not start the Roblox obfuscator") from exc
        if "OpenSSL is unavailable" in result.stdout + result.stderr:
            raise RuntimeError("Roblox obfuscation could not obtain randomness from OpenSSL")
        if result.returncode:
            output = result.stdout + result.stderr
            if "Parsing Error" in output or "Lexing Error" in output:
                raise ValueError(
                    "Invalid or unsupported Luau syntax; Roblox mode does not "
                    "support type annotations or interpolated strings"
                )
            raise RuntimeError("Roblox obfuscation failed")
        if not output_path.is_file() or output_path.stat().st_size > _ROBLOX_OUTPUT_LIMIT:
            raise RuntimeError("Roblox obfuscation produced missing or oversized output")
        return output_path.read_text(encoding="utf-8")


def _minify(source: str) -> str:
    """Remove comments and whitespace without changing the contents of tokens."""
    lexer = LuaLexer(InputStream(source))
    return " ".join(
        token.text for token in lexer.getAllTokens()
        if token.channel == Token.DEFAULT_CHANNEL
    )


def _name() -> str:
    return "_" + secrets.token_hex(8)


def _encode(source: str, chunk_size: int) -> str:
    data = source.encode("utf-8")
    chunks = []
    for index, start in enumerate(range(0, len(data), chunk_size), 1):
        key = secrets.randbelow(256)
        step = secrets.randbelow(255) + 1
        encoded = bytes((byte + key + (i + 1) * step) % 256
                        for i, byte in enumerate(data[start:start + chunk_size]))
        literal = '"' + ''.join(f'\\{byte:03d}' for byte in encoded) + '"'
        chunks.append(f'{{{index},{key},{step},{literal}}}')
    # SystemRandom avoids the predictable state of the default PRNG.
    secrets.SystemRandom().shuffle(chunks)

    table, pieces, entry, chars, i, chunk, loader, err = (_name() for _ in range(8))
    return (
        f'local {table}={{{",".join(chunks)}}};local {pieces}={{}};'
        f'for _,{entry} in ipairs({table}) do local {chars}={{}};'
        f'for {i}=1,#{entry}[4] do '
        f'{chars}[{i}]=string.char((string.byte({entry}[4],{i})-'
        f'{entry}[2]-{i}*{entry}[3])%256) end;'
        f'{pieces}[{entry}[1]]=table.concat({chars}) end;'
        f'local {chunk}=table.concat({pieces});local {loader},{err};'
        f'if _VERSION=="Lua 5.1" and loadstring then {loader},{err}=loadstring({chunk},"=(obfuscated)");'
        f'if {loader} and setfenv and getfenv then setfenv({loader},getfenv(1)) end '
        f'elseif load then {loader},{err}=load({chunk},"=(obfuscated)","t",_ENV) '
        f'else error("Obfuscated code requires load or loadstring") end;'
        f'if not {loader} then error({err}) end;return {loader}(...)'
    )


def obfuscate(source: str, strength: str = "strong") -> str:
    """Validate Lua and return runnable source at the requested strength.

    Medium and strong modes require a runtime that permits dynamic loading.
    Obfuscation makes inspection harder; it cannot keep client-side code secret.
    """
    if strength == "roblox":
        return _obfuscate_roblox(source)

    try:
        ast.parse(source)
    except Exception as exc:
        raise ValueError(f"Lua syntax error: {exc}") from exc

    cleaned = _minify(source)
    chunk_size = STRENGTH_LEVELS.get(strength, STRENGTH_LEVELS["strong"])
    return _encode(cleaned, chunk_size) if chunk_size else cleaned
