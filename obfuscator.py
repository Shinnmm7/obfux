import random
import string
from luaparser import ast, astnodes

STRENGTH_LEVELS = {
    "light":   {"rename": True, "strings": False, "junk": False, "cflow": False},
    "medium":  {"rename": True, "strings": True, "junk": False, "cflow": False},
    "strong":  {"rename": True, "strings": True, "junk": True, "opaque": True, "cflow": True},
}

def rand_name(length=12):
    return "_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=length))

def walk_tree(node):
    yield node
    for attr_name, attr_value in vars(node).items():
        if isinstance(attr_value, astnodes.Node):
            yield from walk_tree(attr_value)
        elif isinstance(attr_value, list):
            for item in attr_value:
                if isinstance(item, astnodes.Node):
                    yield from walk_tree(item)

def xor_encrypt_bytes(data: bytes, key: str) -> list:
    return [b ^ ord(key[i % len(key)]) for i, b in enumerate(data)]

def obfuscate(source: str, strength: str = "strong") -> str:
    cfg = STRENGTH_LEVELS.get(strength, STRENGTH_LEVELS["strong"])
    
    try:
        tree = ast.parse(source)
    except Exception as e:
        raise ValueError(f"Lua syntax error: {e}")

    # PASS 1: Variable Renaming
    if cfg["rename"]:
        var_map = {}
        for node in walk_tree(tree):
            if isinstance(node, astnodes.LocalAssign):
                for target in node.targets:
                    if isinstance(target, astnodes.Name) and target.id not in var_map:
                        var_map[target.id] = rand_name()
            elif isinstance(node, (astnodes.Function, astnodes.LocalFunction)):
                for arg in node.args:
                    if isinstance(arg, astnodes.Name) and arg.id not in var_map:
                        var_map[arg.id] = rand_name()
            elif isinstance(node, astnodes.Forin):
                for target in node.targets:
                    if isinstance(target, astnodes.Name) and target.id not in var_map:
                        var_map[target.id] = rand_name()
            elif isinstance(node, astnodes.Fornum):
                if isinstance(node.target, astnodes.Name) and node.target.id not in var_map:
                    var_map[node.target.id] = rand_name()
        
        for node in walk_tree(tree):
            if isinstance(node, astnodes.Name) and node.id in var_map:
                node.id = var_map[node.id]
            elif isinstance(node, astnodes.LocalAssign):
                for target in node.targets:
                    if isinstance(target, astnodes.Name) and target.id in var_map:
                        target.id = var_map[target.id]
            elif isinstance(node, (astnodes.Function, astnodes.LocalFunction)):
                for arg in node.args:
                    if isinstance(arg, astnodes.Name) and arg.id in var_map:
                        arg.id = var_map[arg.id]
            elif isinstance(node, astnodes.Forin):
                for target in node.targets:
                    if isinstance(target, astnodes.Name) and target.id in var_map:
                        target.id = var_map[target.id]
            elif isinstance(node, astnodes.Fornum):
                if isinstance(node.target, astnodes.Name) and node.target.id in var_map:
                    node.target.id = var_map[node.target.id]

    current_source = ast.to_lua_source(tree)
    
    try:
        tree = ast.parse(current_source)
    except Exception:
        pass

    # PASS 2: String Encryption
    if cfg["strings"]:
        strings_to_encrypt = []
        for node in walk_tree(tree):
            if isinstance(node, astnodes.String) and node.start_char is not None:
                strings_to_encrypt.append(node)
        
        strings_to_encrypt.sort(key=lambda n: n.start_char, reverse=True)
        
        if strings_to_encrypt:
            global_key = rand_name(8)
            for node in strings_to_encrypt:
                encrypted_bytes = xor_encrypt_bytes(node.s, global_key)
                byte_array = "{" + ",".join(map(str, encrypted_bytes)) + "}"
                replacement = f'__DECRYPT({byte_array}, "{global_key}")'
                current_source = current_source[:node.start_char] + replacement + current_source[node.stop_char+1:]

    # PASS 3: Control Flow Flattening (THE GAME CHANGER)
    if cfg["cflow"]:
        # Split source into chunks and wrap in state machine
        lines = current_source.split('\n')
        if len(lines) > 10:
            chunk_size = len(lines) // 4
            chunks = []
            for i in range(0, len(lines), chunk_size):
                chunks.append('\n'.join(lines[i:i+chunk_size]))
            
            if len(chunks) > 1:
                state_var = rand_name()
                flattened = f"""
do
    local {state_var} = 0
    while true do
        if {state_var} == 0 then
{chunks[0]}
            {state_var} = {random.randint(1, 999)}
        elseif {state_var} == {random.randint(1, 999)} then
{chunks[1] if len(chunks) > 1 else ''}
            {state_var} = {random.randint(1, 999)}
        elseif {state_var} == {random.randint(1, 999)} then
{chunks[2] if len(chunks) > 2 else ''}
            {state_var} = {random.randint(1, 999)}
        else
{chunks[3] if len(chunks) > 3 else ''}
            break
        end
    end
end
"""
                current_source = flattened

    # PASS 4: Opaque Predicates & Junk
    if cfg["junk"] or cfg["opaque"]:
        fake_math1 = random.randint(1000, 9999)
        fake_math2 = random.randint(1000, 9999)
        opaque_check = f"""
do
    local __integrity_check = ({fake_math1} * {fake_math2})
    if __integrity_check ~= {fake_math1 * fake_math2} + {random.randint(1, 5)} then
        error("Tamper Detected: Execution Halted")
    end
end
"""
        current_source = opaque_check + "\n" + current_source

    # PASS 5: Runtime Decryption Function
    if cfg["strings"]:
        runtime_decryptor = """
local function __DECRYPT(bytes, key)
    local out = {}
    local key_len = #key
    for i = 1, #bytes do
        local char_code = bytes[i] ~ string.byte(key, ((i - 1) % key_len) + 1)
        out[i] = string.char(char_code)
    end
    return table.concat(out)
end
"""
        current_source = runtime_decryptor + "\n" + current_source

    return current_source
