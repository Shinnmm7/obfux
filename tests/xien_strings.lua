package.path = 'vendor/prometheus/src/?.lua;' .. package.path
local Pipeline = require('prometheus.pipeline')
local presets = require('presets')
assert(presets.Strong.Steps[2].Name == 'EncryptStrings', 'upstream preset changed')
assert(presets.Xien.Steps[2].Name == 'XienStrings')

local bytes = {}
for i = 0, 255 do bytes[#bytes + 1] = string.char(i) end
local payload = table.concat(bytes) .. 'héllo'
local source = 'local function value() return ' .. string.format('%q', payload)
    .. ' end; local t = {field = value()}; return value(), "", "\\000", t.field, "a" .. "b"'
local seen = {}
for seed = 1, 4 do
    local pipeline = Pipeline:fromConfig({LuaVersion = 'Lua51', Seed = seed,
        Steps = {{Name = 'XienStrings', Settings = {}}}})
    local output = pipeline:apply(source)
    assert(not output:find('35184372088832', 1, true), 'upstream decoder remains')
    assert(not seen[output], 'literal encoding did not vary across builds')
    seen[output] = true
    local a, b, c, d, e = assert(loadstring(output))()
    assert(a == payload and b == '' and c == '\0' and d == payload and e == 'ab')
end

-- Repeated calls decode again rather than retaining plaintext in a string table.
local pipeline = Pipeline:fromConfig({LuaVersion = 'Lua51', Seed = 9,
    Steps = {{Name = 'XienStrings', Settings = {}}}})
local output = pipeline:apply('return function() return "cache-probe" end')
local originalChar, calls = string.char, 0
string.char = function(...) calls = calls + 1; return originalChar(...) end
local ok, message = pcall(function()
    local value = assert(loadstring(output))()
    assert(value() == 'cache-probe')
    local first = calls
    assert(value() == 'cache-probe' and calls > first, 'plaintext string was cached')
end)
string.char = originalChar
assert(ok, message)
print('Xien literal byte fidelity, schema variation and no-cache checks passed')
