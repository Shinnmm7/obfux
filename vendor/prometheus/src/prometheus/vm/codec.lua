-- Nebula modification: keyed records decoded on demand, without a plaintext cache.
-- This reversible encoding and checksum are obfuscation, not cryptographic secrecy.
local Codec = {}
local MOD = 2147483647

-- Parameters are shared by the emitter and its generated decoder, never global
-- mutable state: independent builds can safely use different record schemas.
function Codec.new()
    local tags, used = {}, {}
    for i = 0, 10 do
        local tag
        repeat tag = math.random(0, 255) until not used[tag]
        used[tag], tags[i] = true, tag
    end
    local multipliers = {16807, 48271, 69621, 40692}
    return {tags = tags, multiplier = multipliers[math.random(#multipliers)],
        increment = math.random(1, 1048575), feedback = math.random(1, 65535),
        indexSalt = math.random(65536, 1048575), nonceSalt = math.random(1, 65535)}
end

function Codec.encode(value, key, index, length, schema)
    assert(schema, 'Missing VM record schema')
    local tags = schema.tags
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
        if kind == 'nil' then byte(tags[0])
        elseif kind == 'boolean' then byte(v and tags[5] or tags[6])
        elseif kind == 'string' then byte(tags[4]); text(v)
        elseif kind == 'table' then
            byte(tags[2]); count = count or #v; uint(count)
            for i = 1, count do write(v[i]) end
        elseif kind == 'number' then
            if v ~= v then byte(tags[9])
            elseif v == math.huge then byte(tags[7])
            elseif v == -math.huge then byte(tags[8])
            elseif v == 0 and 1 / v < 0 then byte(tags[10])
            elseif v == math.floor(v) and math.abs(v) <= 1073741823 then
                byte(tags[1]); uint(v < 0 and -v * 2 - 1 or v * 2)
            else byte(tags[3]); text(string.format('%.17g', v)) end
        else error('Unsupported VM record value: ' .. kind) end
    end
    write(value, length)
    local nonce = math.random(1, 2147483646)
    local state = (key + index * schema.indexSalt + nonce * schema.nonceSalt) % MOD
    if state == 0 then state = 1 end
    local first, second = (key + index + nonce) % 65521, 0
    local output, previous = {}, nonce % 256
    for i, valueByte in ipairs(bytes) do
        state = (state * schema.multiplier + schema.increment + previous * schema.feedback) % MOD
        previous = (valueByte + state % 256) % 256
        output[i] = string.char(previous)
        first = (first + valueByte) % 65521
        second = (second + first) % 65521
    end
    return {table.concat(output), first + second * 65521, nonce}
end

local runtime = [=[
local nativeByte, nativeChar, nativeConcat = string.byte, string.char, table.concat
local nativeType = type
local function decode(record, key, index)
    local function invalid() nativeError('VM record integrity check failed', 0) end
    if nativeType(record) ~= 'table' or nativeType(record[1]) ~= 'string' then invalid() end
    local nonce = record[3]
    if nativeType(nonce) ~= 'number' or nonce < 1 or nonce > 2147483646 or nonce % 1 ~= 0 then invalid() end
    local cipher, position = record[1], 0
    local state = (key + index * __INDEX_SALT__ + nonce * __NONCE_SALT__) % 2147483647
    if state == 0 then state = 1 end
    local first, second = (key + index + nonce) % 65521, 0
    local previous = nonce % 256
    local function byte()
        position = position + 1
        if position > #cipher then invalid() end
        state = (state * __MULTIPLIER__ + __INCREMENT__ + previous * __FEEDBACK__) % 2147483647
        previous = nativeByte(cipher, position)
        local value = (previous - state % 256) % 256
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
        if tag == __TAG_0__ then return nil
        elseif tag == __TAG_1__ then
            local n = uint()
            if n % 2 == 0 then return n / 2 end
            return -(n + 1) / 2
        elseif tag == __TAG_2__ then
            local count, values = uint(), {}
            if count > #cipher - position then invalid() end
            for i = 1, count do values[i] = read(depth + 1) end
            return values
        elseif tag == __TAG_3__ then
            local value = nativeTonumber(text())
            if value == nil then invalid() end
            return value
        elseif tag == __TAG_4__ then return text()
        elseif tag == __TAG_5__ then return true
        elseif tag == __TAG_6__ then return false
        elseif tag == __TAG_7__ then return 1 / 0
        elseif tag == __TAG_8__ then return -1 / 0
        elseif tag == __TAG_9__ then return 0 / 0
        elseif tag == __TAG_10__ then return -1 / (1 / 0)
        end
        invalid()
    end
    local value = read(0)
    if position ~= #cipher or first + second * 65521 ~= record[2] then invalid() end
    return value
end
]=]

function Codec.runtime(schema)
    local parameters = {INDEX_SALT = schema.indexSalt, NONCE_SALT = schema.nonceSalt,
        MULTIPLIER = schema.multiplier, INCREMENT = schema.increment, FEEDBACK = schema.feedback}
    local source = runtime:gsub('__TAG_(%d+)__', function(tag)
        return tostring(assert(schema.tags[tonumber(tag)]))
    end)
    return (source:gsub('__(%u[%u_]*)__', function(name)
        return tostring(assert(parameters[name], 'Missing VM decoder parameter'))
    end))
end
return Codec
