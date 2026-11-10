import asyncio
import io
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException, UploadFile

from main import obfuscate_cmd, obfuscate_endpoint
from obfuscator import obfuscate


LUA_VERSIONS = [v for v in ('lua5.1', 'lua5.2', 'lua5.3', 'lua5.4') if shutil.which(v)]
LUAU = os.environ.get('LUAU_BIN') or shutil.which('luau')
ROBLOX_COMPILER = shutil.which('lua5.1') and shutil.which('openssl')


class ObfuscatorTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('lua5.1'), 'Lua 5.1 required')
    def test_xien_literal_records(self):
        subprocess.run(['lua5.1', 'tests/xien_strings.lua'], check=True, capture_output=True,
                       timeout=20, cwd=Path(__file__).resolve().parents[1])

    @unittest.skipUnless(shutil.which('lua5.1'), 'Lua 5.1 required')
    def test_vm_record_integrity_and_startup_exposure(self):
        subprocess.run(['lua5.1', 'tests/vm_codec.lua'], check=True, capture_output=True,
                       timeout=20, cwd=Path(__file__).resolve().parents[1])

    def test_invalid_lua_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Lua syntax error'):
            obfuscate('local function broken(')

    def test_strong_output_hides_source_and_is_randomized(self):
        source = 'local secret = "unique cleartext message"; print(secret)'
        first = obfuscate(source)
        second = obfuscate(source)
        self.assertNotIn('unique cleartext message', first)
        self.assertNotIn('secret', first)
        self.assertNotEqual(first, second)

    def test_token_cleanup_preserves_literals(self):
        result = obfuscate('local s = "-- not a comment" -- comment\nreturn s', 'light')
        self.assertIn('"-- not a comment"', result)
        self.assertNotIn('-- comment', result)

    @unittest.skipUnless(LUA_VERSIONS, 'Lua interpreter required')
    def test_outputs_preserve_execution_and_returns(self):
        # Includes nested scopes, table keys, varargs, long strings, escape sequences,
        # comments, UTF-8, and enough statements to span multiple encoded chunks.
        source = '''
local value = "outer"
local obj = { value = "key" }
local function f(value, ...)
    local s = [=[-- content \" hi]=]
    return value .. ":" .. s, ...
end
-- an actual comment
local a, b, c = f(obj.value, "héllo", "third")
for i = 1, 25 do value = value .. tostring(i) end
return a, b, c, value
'''
        for version in LUA_VERSIONS:
            for strength in ('light', 'medium', 'strong'):
                with self.subTest(version=version, strength=strength):
                    self.compare_execution(version, source, strength)

    def compare_execution(self, version, source, strength):
        runner = '''
local filename = arg[1]
local compile = loadfile
local f, err = compile(filename)
assert(f, err)
local results = {f("arg1", "arg2")}
for i = 1, #results do print(results[i]) end
'''
        with tempfile.TemporaryDirectory() as tmp:
            original = Path(tmp, 'original.lua')
            output = Path(tmp, 'output.lua')
            script = Path(tmp, 'run.lua')
            original.write_text(source, encoding='utf-8')
            output.write_text(obfuscate(source, strength), encoding='utf-8')
            script.write_text(runner, encoding='utf-8')
            def run(path):
                return subprocess.run([version, str(script), str(path)], capture_output=True, check=True).stdout
            self.assertEqual(run(original), run(output))

    @unittest.skipUnless(LUA_VERSIONS, 'Lua interpreter required')
    def test_chunk_varargs_and_custom_environment(self):
        source = 'return marker, ...'
        runner = '''
local path = arg[1]
local env = setmetatable({marker="custom"}, {__index=_G})
local f
if _VERSION == "Lua 5.1" then f = assert(loadfile(path)); setfenv(f, env)
else f = assert(loadfile(path, "t", env)) end
local a, b, c = f("first", "second")
assert(a == "custom" and b == "first" and c == "second")
'''
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp, 'run.lua')
            script.write_text(runner)
            for version in LUA_VERSIONS:
                for strength in ('light', 'medium', 'strong'):
                    with self.subTest(version=version, strength=strength):
                        output = Path(tmp, 'output.lua')
                        output.write_text(obfuscate(source, strength))
                        subprocess.run([version, str(script), str(output)], check=True, capture_output=True)

    def test_endpoint_reports_bad_input(self):
        for data in (b'\xff', b'local function broken('):
            with self.subTest(data=data), self.assertRaises(HTTPException) as caught:
                asyncio.run(obfuscate_endpoint(UploadFile(filename='test.lua', file=io.BytesIO(data)), 'strong'))
            self.assertEqual(caught.exception.status_code, 400)

    def test_roblox_mode_reports_missing_runtime(self):
        with patch('obfuscator.shutil.which', return_value=None):
            with self.assertRaisesRegex(RuntimeError, 'Lua 5.1 and OpenSSL'):
                obfuscate('print("hi")', 'roblox')
            with self.assertRaises(HTTPException) as caught:
                asyncio.run(obfuscate_endpoint(
                    UploadFile(filename='test.luau', file=io.BytesIO(b'print("hi")')), 'roblox'))
            self.assertEqual(caught.exception.status_code, 503)

    def test_discord_reports_missing_server_tools(self):
        interaction = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        attachment = MagicMock(filename='test.lua')
        attachment.read = AsyncMock(return_value=b'print("hi")')
        with patch('obfuscator.shutil.which', return_value=None):
            asyncio.run(obfuscate_cmd.callback(interaction, attachment, 'roblox'))
        interaction.followup.send.assert_awaited_once()
        message = interaction.followup.send.call_args.args[0]
        self.assertIn('Obfuscation unavailable', message)
        self.assertIn('repository Dockerfile', message)
        self.assertNotIn('Unexpected Error', message)

    def test_roblox_mode_rejects_predictable_randomness(self):
        result = subprocess.CompletedProcess([], 0, 'OpenSSL is unavailable. Falling back to unix time.', '')
        with patch('obfuscator.shutil.which', return_value='/usr/bin/tool'), \
             patch('obfuscator.subprocess.run', return_value=result):
            with self.assertRaisesRegex(RuntimeError, 'randomness from OpenSSL'):
                obfuscate('print("hi")', 'roblox')

    def test_roblox_mode_reports_busy(self):
        with patch('obfuscator.shutil.which', return_value='/usr/bin/tool'), \
             patch('obfuscator._ROBLOX_WORKERS') as workers:
            workers.acquire.return_value = False
            with self.assertRaisesRegex(RuntimeError, 'busy'):
                obfuscate('print("hi")', 'roblox')
            workers.release.assert_not_called()

    @unittest.skipUnless(ROBLOX_COMPILER, 'Lua 5.1 and OpenSSL required')
    def test_roblox_mode_rejects_unsupported_luau(self):
        for source in ('local x: number = 1', 'print(`hello`)'):
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, 'unsupported Luau'):
                obfuscate(source, 'roblox')

    @unittest.skipUnless(ROBLOX_COMPILER and LUAU, 'Lua 5.1, OpenSSL and Luau CLI required')
    def test_roblox_vm_preserves_luau_execution(self):
        source = '''
local marker = "a unique test string"
local function sum(n)
    local total = 0
    for i = 1, n do
        if i == 2 then continue end
        total += i
    end
    return function() return total end
end
print(game:GetService("Players").Name, marker, sum(5)())
'''
        results = [obfuscate(source, 'roblox') for _ in range(2)]
        self.assertNotEqual(*results)
        with tempfile.TemporaryDirectory() as tmp:
            original = Path(tmp, 'original.luau')
            output = Path(tmp, 'output.luau')
            mock_roblox = 'game = {GetService = function(self, name) return {Name = name} end}\n'
            original.write_text(mock_roblox + source, encoding='utf-8')
            expected = subprocess.run([LUAU, str(original)], check=True, capture_output=True, timeout=20).stdout
            for result in results:
                self.assertNotIn('a unique test string', result)
                # The generated VM should not need the decoded source passed to loadstring.
                output.write_text(mock_roblox + 'loadstring = function() error("unexpected loadstring") end\n' + result,
                                  encoding='utf-8')
                actual = subprocess.run([LUAU, str(output)], check=True, capture_output=True, timeout=20).stdout
                self.assertEqual(expected, actual)

    @unittest.skipUnless(ROBLOX_COMPILER and LUAU, 'Lua 5.1, OpenSSL and Luau CLI required')
    def test_roblox_vm_preserves_calls_and_numeric_constants(self):
        source = '''
local function pack(...) return {n=select('#', ...), ...} end
local function make(v) return function(...) return v, ... end end
local function tail(f, ...) return f(...) end
local co = coroutine.create(function()
    local first = coroutine.yield('paused', 1.2345678901234567)
    return first, -1 / (1 / 0), 1e300, 1e-300
end)
print(coroutine.resume(co))
print(coroutine.resume(co, 'resumed'))
local r = pack(tail(make('closure'), nil, false, 'last'))
print(r.n, r[1], r[2], r[3], r[4])
for i = 1, 3 do print(make(i)()) end
local t = setmetatable({}, {__add=function() return 99 end})
print(t+t)
'''
        result = obfuscate(source, 'roblox')
        with tempfile.TemporaryDirectory() as tmp:
            original, output = Path(tmp, 'original.luau'), Path(tmp, 'output.luau')
            original.write_text(source, encoding='utf-8')
            output.write_text(result, encoding='utf-8')
            expected = subprocess.run([LUAU, str(original)], check=True, capture_output=True, timeout=20).stdout
            actual = subprocess.run([LUAU, str(output)], check=True, capture_output=True, timeout=20).stdout
            self.assertEqual(expected, actual)


if __name__ == '__main__':
    unittest.main()
