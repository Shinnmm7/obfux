"""Lua source obfuscation with a portable, randomized runtime decoder."""

import secrets

from antlr4 import InputStream, Token
from luaparser import ast
from luaparser.parser.LuaLexer import LuaLexer


STRENGTH_LEVELS = {"light": 0, "medium": 128, "strong": 32}


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
    try:
        ast.parse(source)
    except Exception as exc:
        raise ValueError(f"Lua syntax error: {exc}") from exc

    cleaned = _minify(source)
    chunk_size = STRENGTH_LEVELS.get(strength, STRENGTH_LEVELS["strong"])
    return _encode(cleaned, chunk_size) if chunk_size else cleaned
