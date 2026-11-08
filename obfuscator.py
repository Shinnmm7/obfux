import random
import string
from luaparser import ast, astnodes

STRENGTH_LEVELS = {
    "light":   {"rename": True, "junk": False},
    "medium":  {"rename": True, "junk": True},
    "strong":  {"rename": True, "junk": True, "wrap": True},
}

def rand_name(length=12):
    return "_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=length))

def walk_tree(node):
    """Recursively walk all nodes in the AST"""
    yield node
    if hasattr(node, 'children'):
        for child in node.children:
            if child is not None:
                yield from walk_tree(child)

def obfuscate(source: str, strength: str = "strong") -> str:
    cfg = STRENGTH_LEVELS.get(strength, STRENGTH_LEVELS["strong"])
    
    try:
        tree = ast.parse(source)
    except Exception as e:
        raise ValueError(f"Lua syntax error: {e}")

    # --- Pass 1: Variable Renaming ---
    if cfg["rename"]:
        var_map = {}
        
        # First pass: collect all local variable names
        for node in walk_tree(tree):
            if isinstance(node, astnodes.LocalAssign):
                for target in node.targets:
                    if isinstance(target, astnodes.Name) and target.id not in var_map:
                        var_map[target.id] = rand_name()
        
        # Second pass: rename all references
        for node in walk_tree(tree):
            if isinstance(node, astnodes.Name):
                if node.id in var_map:
                    node.id = var_map[node.id]
            elif isinstance(node, astnodes.LocalAssign):
                for target in node.targets:
                    if isinstance(target, astnodes.Name) and target.id in var_map:
                        target.id = var_map[target.id]

    # --- Pass 2: Junk Code Insertion ---
    if cfg["junk"]:
        for node in walk_tree(tree):
            if isinstance(node, astnodes.Block) and len(node.body) > 0:
                if random.random() < 0.3:
                    junk_var = rand_name()
                    junk_val = random.randint(1000, 99999)
                    try:
                        junk_code = ast.parse(f"local {junk_var} = {junk_val}")
                        if junk_code.body:
                            insert_pos = random.randint(0, len(node.body))
                            node.body.insert(insert_pos, junk_code.body[0])
                    except:
                        pass  # Skip if junk insertion fails

    result = ast.to_lua_source(tree)

    # --- Pass 3: Control Flow Wrapping ---
    if cfg["wrap"]:
        result = f"do\n    local __state = {random.randint(1, 999)}\n    {result}\nend"

    return result
