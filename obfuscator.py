import random
import string
from luaparser import ast, astnodes

STRENGTH_LEVELS = {
    "light":   {"rename": True, "strings": False, "junk": False},
    "medium":  {"rename": True, "strings": True, "junk": False},
    "strong":  {"rename": True, "strings": True, "junk": True, "opaque": True},
}

def rand_name(length=12):
    return "_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=length))

def walk_tree(node):
    """Robustly recursively walk all nodes in the luaparser AST"""
    yield node
    for attr_name, attr_value in vars(node).items():
        if isinstance(attr_value, astnodes.Node):
            yield from walk_tree(attr_value)
        elif isinstance(attr_value, list):
            for item in attr_value:
                if isinstance(item, astnodes.Node):
                    yield from walk_tree(item)

def xor_encrypt_bytes(data: bytes, key: str) -> list:
    """XOR encrypt a byte string with a repeating key"""
    return [b ^ ord(key[i % len(key)]) for i, b in enumerate(data)]

def obfuscate(source: str, strength: str = "strong") -> str:
    cfg = STRENGTH_LEVELS.get(strength, STRENGTH_LEVELS["strong"])
    
    try:
        tree = ast.parse(source)
    except Exception as e:
        raise ValueError(f"Lua syntax error: {e}")

    # ==========================================
    # PASS 1: Variable & Argument Renaming
    # ==========================================
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

    # Re-serialize to get updated source with renamed variables
    current_source = ast.to_lua_source(tree)
    
    # Re-parse to get accurate character positions for the new source
    try:
        tree = ast.parse(current_source)
    except Exception:
        pass # Fallback to current_source if re-parsing fails

    # ==========================================
    # PASS 2: String Encryption (Position-Based Injection)
    # ==========================================
    if cfg["strings"]:
        strings_to_encrypt = []
        for node in walk_tree(tree):
            if isinstance(node, astnodes.String) and node.start_char is not None:
                strings_to_encrypt.append(node)
        
        # Sort by start_char DESCENDING so replacing from end to start doesn't shift indices
        strings_to_encrypt.sort(key=lambda n: n.start_char, reverse=True)
        
        if strings_to_encrypt:
            global_key = rand_name(8)
            for node in strings_to_encrypt:
                encrypted_bytes = xor_encrypt_bytes(node.s, global_key)
                byte_array = "{" + ",".join(map(str, encrypted_bytes)) + "}"
                replacement = f'__DECRYPT({byte_array}, "{global_key}")'
                
                # Inject directly into the source string
                current_source = current_source[:node.start_char] + replacement + current_source[node.stop_char+1:]

    # ==========================================
    # PASS 3: Opaque Predicates & Junk Code
    # ==========================================
    if cfg["junk"] or cfg["opaque"]:
        # Prepend an opaque predicate that always evaluates to false, but looks complex
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

    # ==========================================
    # PASS 4: Prepend Runtime Decryption Function
    # ==========================================
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

    # ==========================================
    # PASS 5: Final Control Flow Wrapping
    # ==========================================
    if cfg["strong"]:
        current_source = f"do\n    local __state = {random.randint(1, 9999)}\n    {current_source}\nend"

    return current_source
