import random
import string
import base64
from luaparser import ast, astnodes

# ==========================================
# CONFIGURATION
# ==========================================
STRENGTH_LEVELS = {
    "light":   {"strings": False, "cflow": False, "junk": False},
    "medium":  {"strings": True,  "cflow": False, "junk": True},
    "strong":  {"strings": True,  "cflow": True,  "junk": True},
}

# ==========================================
# HELPERS
# ==========================================
def rand_name(length=12):
    return "_" + "".join(random.choices(string.ascii_lowercase, k=length))

def xor_encrypt(text: str, key: str) -> list:
    return [ord(c) ^ ord(key[i % len(key)]) for i, c in enumerate(text)]

# ==========================================
# MAIN OBFUSCATOR
# ==========================================
def obfuscate(source: str, strength: str = "strong") -> str:
    cfg = STRENGTH_LEVELS.get(strength, STRENGTH_LEVELS["strong"])
    
    try:
        tree = ast.parse(source)
    except Exception as e:
        raise ValueError(f"Lua syntax error: {e}")

    # --- Pass 1: Variable Renaming ---
    var_map = {}
    class Renamer(ast.ASTVisitor):
        def visit_LocalAssign(self, node):
            for t in node.targets:
                if isinstance(t, astnodes.Id) and t.id not in var_map:
                    var_map[t.id] = rand_name()
                if isinstance(t, astnodes.Id):
                    t.id = var_map[t.id]
            self.generic_visit(node)
        def visit_Id(self, node):
            if node.id in var_map:
                node.id = var_map[node.id]
            self.generic_visit(node)
    Renamer().visit(tree)

    # --- Pass 2: String Encryption ---
    if cfg["strings"]:
        key = rand_name(8)
        class StringEncryptor(ast.ASTVisitor):
            def visit_String(self, node):
                encrypted = xor_encrypt(node.s, key)
                # Replace "hello" with DECRYPT({1,2,3}, "key")
                node.s = f'__LURAPH_DEC({encrypted}, "{key}")'
                node.raw = f'"{node.s}"'
                self.generic_visit(node)
        StringEncryptor().visit(tree)

    # --- Pass 3: Junk Code Insertion ---
    if cfg["junk"]:
        class JunkInserter(ast.ASTVisitor):
            def visit_Block(self, node):
                self.generic_visit(node)
                if random.random() < 0.3 and node.body:
                    junk = ast.parse(f"local {rand_name()} = {random.randint(1,9999)}")
                    node.body.insert(0, junk.body[0])
        JunkInserter().visit(tree)

    # --- Pass 4: Control Flow Flattening (basic) ---
    if cfg["cflow"]:
        # Wrap top-level statements in a dispatcher
        body = tree.body
        if len(body) > 1:
            states = [rand_name() for _ in body]
            dispatcher = f"""
do
    local __state = 0
    while true do
        if __state == 0 then
            {ast.to_lua_source(astnodes.Block(body=body[:len(body)//2]))}
            __state = 1
        elseif __state == 1 then
            {ast.to_lua_source(astnodes.Block(body=body[len(body)//2:]))}
            break
        end
    end
end
"""
            try:
                tree = ast.parse(dispatcher)
            except:
                pass  # Fallback: skip CFF if it breaks syntax

    result = ast.to_lua_source(tree)

    # --- Pass 5: Prepend Decryption Runtime ---
    if cfg["strings"]:
        runtime = '''
local function __LURAPH_DEC(bytes, key)
    local out = {}
    for i, b in ipairs(bytes) do
        out[i] = string.char(b ~ string.byte(key, (i-1) % #key + 1))
    end
    return table.concat(out)
end
'''
        result = runtime + "\n" + result

    return result
