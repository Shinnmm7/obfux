import asyncio
import io
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException, UploadFile

from main import obfuscate_endpoint
from obfuscator import obfuscate


LUA_VERSIONS = [v for v in ('lua5.1', 'lua5.2', 'lua5.3', 'lua5.4') if shutil.which(v)]


class ObfuscatorTests(unittest.TestCase):
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


if __name__ == '__main__':
    unittest.main()
