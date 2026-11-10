-- Exercise the record format independently of the obfuscation pipeline.
package.path = 'vendor/prometheus/src/?.lua;' .. package.path
local Codec = require('prometheus.vm.codec')
local Data = require('prometheus.vm.data')
local Layout = require('prometheus.vm.layout')
local Emit = require('prometheus.vm.emit')
local Opcodes = require('prometheus.vm.opcodes')
local decode = assert(loadstring('local nativeTonumber, nativeError = tonumber, error\n'
    .. Codec.runtime .. '\nreturn decode'))()
local function roundtrip(value, check, length)
    for _, key in ipairs({1, 123456789, 2147483646}) do
        for _, index in ipairs({1, 50000, -1}) do
            local record = Codec.encode(value, key, index, length)
            check(decode(record, key, index))
            local mutated = {string.char((record[1]:byte(1) + 1) % 256) .. record[1]:sub(2), record[2]}
            assert(not pcall(decode, mutated, key, index), 'modified payload accepted')
            assert(not pcall(decode, record, key, index + 1), 'relocated payload accepted')
            assert(not pcall(decode, {record[1], record[2] + 1}, key, index), 'modified checksum accepted')
        end
    end
end
for _, value in ipairs({false, true, '', '\0\255héllo', -1, 0, 1073741823, -1073741823,
        1.2345678901234567, 1e300, 1e-300, math.huge, -math.huge}) do
    roundtrip(value, function(result) assert(result == value, 'roundtrip mismatch') end)
end
roundtrip(nil, function(value) assert(value == nil) end)
roundtrip(-1 / math.huge, function(value) assert(value == 0 and 1 / value == -math.huge) end)
roundtrip(0/0, function(value) assert(value ~= value) end)
roundtrip({23, nil, {-1, 42}, nil, 9}, function(value)
    assert(value[1] == 23 and value[2] == nil and value[3][1] == -1 and value[3][2] == 42)
    assert(value[4] == nil and value[5] == 9)
end, 5)
local layout = Layout.new()
local proto = {code = {{Opcodes.LOAD, 1, 1}, {Opcodes.RETURN1, 1}},
    constants = {'private-probe-string'}, captures = {}, params = {}, vararg = false,
    maxRegister = 1, children = {}}
local data, count, root = Data.encode(proto, layout)
local rebuilt = assert(loadstring(Data.rebuild .. '\nreturn rebuild(' .. data .. ',' .. count .. ',' .. root .. ')'))()
local P = rebuilt[1]
assert(type(P[layout.fields.code][1][1]) == 'string', 'startup exposed decoded instructions')
assert(type(P[layout.fields.constants][1][1]) == 'string')
assert(P[layout.fields.constants][1][1] ~= 'private-probe-string', 'startup exposed decoded constant')
assert(assert(loadstring(Emit.source(proto, layout)))() == 'private-probe-string')
-- Corrupt the first record after reconstruction: it must fail before returning any value.
local originalRebuild = Data.rebuild
Data.rebuild = originalRebuild .. '\nlocal original = rebuild\nrebuild = function(...) local p = original(...); '
    .. 'local r = p[1][' .. layout.fields.code .. '][1]; r[2] = r[2] + 1; return p end\n'
local ok, message = pcall(assert(loadstring(Emit.source(proto, layout))))
Data.rebuild = originalRebuild
assert(not ok and tostring(message):find('VM record integrity check failed', 1, true))
print('codec roundtrips, startup exposure and tamper rejection passed')
