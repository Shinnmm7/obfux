-- Xien modification: literal records use a fresh schema and no decoded cache.
-- Reversible obfuscation only; the decoder and its parameters ship with output.
local Step = require('prometheus.step')
local Ast = require('prometheus.ast')
local Parser = require('prometheus.parser')
local Enums = require('prometheus.enums')
local Source = require('prometheus.source')
local visitast = require('prometheus.visitast')
local Codec = require('prometheus.vm.codec')
local hoistVmStrings = require('prometheus.vm.strings')

local XienStrings = Step:extend()
XienStrings.Name = 'Xien Strings'
XienStrings.Description = 'Encode literals with per-build typed records.'
XienStrings.SettingsDescriptor = {}

function XienStrings:init() end

function XienStrings:apply(ast)
    -- Only interpreter literals are hoisted. User constants remain in VM records.
    -- This keeps repeated type/error literals off the instruction-fetch hot path.
    hoistVmStrings(ast)
    local schema = Codec.new()
    local decoder = Ast.LocalSymbol('_xien_decode')
    local index = 0
    visitast(ast, nil, function(node)
        if node.kind == Ast.AstKind.StringExpression then
            index = index + 1
            local key = math.random(1, 2147483646)
            local record = Codec.encode(node.value, key, index, nil, schema)
            local entries = {}
            for i = 1, 3 do entries[i] = Ast.TableEntry(Ast.ConstantNode(record[i])) end
            return Source.inherit(Ast.FunctionCallExpression(Ast.VariableExpression(decoder), {
                Ast.TableConstructorExpression(entries), Ast.NumberExpression(key),
                Ast.NumberExpression(index),
            }), node)
        end
    end)
    if index == 0 then return ast end

    -- Insert after visiting literals so the decoder cannot encode its own strings.
    local code = 'return (function()\nlocal nativeTonumber, nativeError = tonumber, error\n'
        .. Codec.runtime(schema) .. '\nreturn decode\nend)()'
    local generated = Parser:new({LuaVersion = Enums.LuaVersion.Lua51})
        :parse(code, Source.internal('XienStrings.Decoder', code))
    local expression = generated.body.statements[1].args[1]
    table.insert(ast.body.statements, 1, Source.fill(
        Ast.LocalVariableDeclaration({decoder}, {expression}), Source.generated('XienStrings')))
    return ast
end

return XienStrings
