-- Exercise the record format independently of the obfuscation pipeline.
package.path = 'vendor/prometheus/src/?.lua;' .. package.path
local Codec = require('prometheus.vm.codec')
local Data = require('prometheus.vm.data')
local Layout = require('prometheus.vm.layout')
local Emit = require('prometheus.vm.emit')
local Opcodes = require('prometheus.vm.opcodes')
local schema, decode
local function decoder(format)
    return assert(loadstring('local nativeTonumber, nativeError = tonumber, error\n'
        .. Codec.runtime(format) .. '\nreturn decode'))()
end
local function roundtrip(value, check, length)
    for _, key in ipairs({1, 123456789, 2147483646}) do
        for _, index in ipairs({1, 50000, -1}) do
            local record = Codec.encode(value, key, index, length, schema)
            check(decode(record, key, index))
            local mutated = {string.char((record[1]:byte(1) + 1) % 256) .. record[1]:sub(2), record[2], record[3]}
            assert(not pcall(decode, mutated, key, index), 'modified payload accepted')
            assert(not pcall(decode, record, key, index + 1), 'relocated payload accepted')
            assert(not pcall(decode, record, key + 1, index), 'wrong prototype key accepted')
            local nonce = record[3] % 2147483646 + 1
            assert(not pcall(decode, {record[1], record[2], nonce}, key, index), 'modified nonce accepted')
            assert(not pcall(decode, {record[1], record[2]}, key, index), 'missing nonce accepted')
            assert(not pcall(decode, {record[1], record[2] + 1, record[3]}, key, index), 'modified checksum accepted')
        end
    end
end
-- Reproducible schemas must each survive the same scalar, sparse and corruption cases.
local decoders = {}
for seed = 1, 8 do
    math.randomseed(seed)
    schema = Codec.new()
    local source = Codec.runtime(schema)
    assert(not decoders[source], 'builds reused a record schema')
    decoders[source] = true
    decode = decoder(schema)
    -- Changing just the tag schema must invalidate a record even when its stream
    -- parameters and checksum are otherwise identical.
    local changed = {}
    for name, value in pairs(schema) do changed[name] = value end
    changed.tags = {}
    for tag, value in pairs(schema.tags) do changed.tags[tag] = value end
    changed.tags[0], changed.tags[4] = changed.tags[4], changed.tags[0]
    local nilRecord = Codec.encode(nil, 123, 1, nil, schema)
    assert(not pcall(decoder(changed), nilRecord, 123, 1), 'incompatible tag schema accepted')
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
end
local layout = Layout.new()
local proto = {code = {{Opcodes.LOAD, 1, 1}, {Opcodes.RETURN1, 1}},
    constants = {'private-probe-string'}, captures = {}, params = {}, vararg = false,
    maxRegister = 1, children = {}}
local data, count, root = Data.encode(proto, layout)
local rebuilt = assert(loadstring(Data.rebuild .. '\nreturn rebuild(' .. data .. ',' .. count .. ',' .. root .. ')'))()
local P = rebuilt[1]
local address = layout:address(1, P[layout.fields.key])
assert(type(P[layout.fields.code][address][1]) == 'string', 'startup exposed decoded instructions')
local addresses = {}
for _, pc in ipairs({1, 2, 3, 10000, 2147483645, 2147483646}) do
    local slot = layout:address(pc, P[layout.fields.key])
    assert(slot >= 0 and slot < 2147483647 and not addresses[slot])
    addresses[slot] = true
end
assert(not pcall(function() layout:address(2147483647, 1) end))
local zeroKey = (-layout.codeStride - layout.codeSalt) % 2147483647
assert(layout:address(1, zeroKey) == 0, 'zero instruction address lost')
assert(P[layout.fields.code][1] == nil and P[layout.fields.code][2] == nil,
    'startup retained program-ordered instructions')
local rawDecode = decoder(layout.codec)
local first = rawDecode(P[layout.fields.code][address], P[layout.fields.key], 1)
assert(first[1] == layout.opcodes.LOAD)
assert(not pcall(rawDecode, P[layout.fields.code][address], P[layout.fields.key], 2),
    'instruction relocation bypassed record binding')
assert(type(P[layout.fields.constants][1][1]) == 'string')
assert(P[layout.fields.constants][1][1] ~= 'private-probe-string', 'startup exposed decoded constant')
assert(assert(loadstring(Emit.source(proto, layout)))() == 'private-probe-string')
-- Corrupt the first record after reconstruction: it must fail before returning any value.
local originalRebuild = Data.rebuild
Data.rebuild = originalRebuild .. '\nlocal original = rebuild\nrebuild = function(...) local p = original(...); '
    .. 'local key = p[1][' .. layout.fields.key .. ']; local r = p[1][' .. layout.fields.code .. ']'
    .. '[(1 * ' .. layout.codeStride .. ' + key + ' .. layout.codeSalt .. ') % 2147483647]; '
    .. 'r[2] = r[2] + 1; return p end\n'
local ok, message = pcall(assert(loadstring(Emit.source(proto, layout))))
Data.rebuild = originalRebuild
assert(not ok and tostring(message):find('VM record integrity check failed', 1, true))
print('codec roundtrips, startup exposure and tamper rejection passed')
