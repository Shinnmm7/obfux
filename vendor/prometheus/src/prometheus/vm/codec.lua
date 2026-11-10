-- Nebula modification: keyed records decoded on demand, without a plaintext cache.
-- This reversible encoding and checksum are obfuscation, not cryptographic secrecy.
local Codec = {}
local MOD = 2147483647

function Codec.encode(value, key, index, length)
    local bytes = {}
    local function byte(n) bytes[#bytes + 1] = n end
    local function uint(n)
        repeat
            local part = n % 128
            n = math.floor(n / 128)
            byte(part + (n > 0 and 128 or 0))
        until n == 0
    end
    local function text(s)
        uint(#s)
        for i = 1, #s do byte(s:byte(i)) end
    end
    local function write(v, count)
        local kind = type(v)
        if kind == 'nil' then byte(0)
        elseif kind == 'boolean' then byte(v and 5 or 6)
        elseif kind == 'string' then byte(4); text(v)
        elseif kind == 'table' then
            byte(2); count = count or #v; uint(count)
            for i = 1, count do write(v[i]) end
        elseif kind == 'number' then
            if v ~= v then byte(9)
            elseif v == math.huge then byte(7)
            elseif v == -math.huge then byte(8)
            elseif v == 0 and 1 / v < 0 then byte(10)
            elseif v == math.floor(v) and math.abs(v) <= 1073741823 then
                byte(1); uint(v < 0 and -v * 2 - 1 or v * 2)
            else byte(3); text(string.format('%.17g', v)) end
        else error('Unsupported VM record value: ' .. kind) end
    end
    write(value, length)
    local state = (key + index * 104729) % MOD
    if state == 0 then state = 1 end
    local first, second = (key + index) % 65521, 0
    local output = {}
    for i, valueByte in ipairs(bytes) do
        state = (state * 48271) % MOD
        output[i] = string.char((valueByte + state % 256) % 256)
        first = (first + valueByte) % 65521
        second = (second + first) % 65521
    end
    return {table.concat(output), first + second * 65521}
end

Codec.runtime = [=[
local nativeByte, nativeChar, nativeConcat = string.byte, string.char, table.concat
local nativeType = type
local function decode(record, key, index)
    local function invalid() nativeError('VM record integrity check failed', 0) end
    if nativeType(record) ~= 'table' or nativeType(record[1]) ~= 'string' then invalid() end
    local cipher, position = record[1], 0
    local state = (key + index * 104729) % 2147483647
    if state == 0 then state = 1 end
    local first, second = (key + index) % 65521, 0
    local function byte()
        position = position + 1
        if position > #cipher then invalid() end
        state = (state * 48271) % 2147483647
        local value = (nativeByte(cipher, position) - state % 256) % 256
        first = (first + value) % 65521
        second = (second + first) % 65521
        return value
    end
    local function uint()
        local value, scale = 0, 1
        for i = 1, 5 do
            local part = byte()
            value = value + (part % 128) * scale
            if part < 128 then return value end
            scale = scale * 128
        end
        invalid()
    end
    local function text()
        local count, chars = uint(), {}
        if count > #cipher - position then invalid() end
        for i = 1, count do chars[i] = nativeChar(byte()) end
        return nativeConcat(chars)
    end
    local read
    read = function(depth)
        if depth > 64 then invalid() end
        local tag = byte()
        if tag == 0 then return nil
        elseif tag == 1 then
            local n = uint()
            if n % 2 == 0 then return n / 2 end
            return -(n + 1) / 2
        elseif tag == 2 then
            local count, values = uint(), {}
            if count > #cipher - position then invalid() end
            for i = 1, count do values[i] = read(depth + 1) end
            return values
        elseif tag == 3 then
            local value = nativeTonumber(text())
            if value == nil then invalid() end
            return value
        elseif tag == 4 then return text()
        elseif tag == 5 then return true
        elseif tag == 6 then return false
        elseif tag == 7 then return 1 / 0
        elseif tag == 8 then return -1 / 0
        elseif tag == 9 then return 0 / 0
        elseif tag == 10 then return -1 / (1 / 0)
        end
        invalid()
    end
    local value = read(0)
    if position ~= #cipher or first + second * 65521 ~= record[2] then invalid() end
    return value
end
]=]
return Codec
