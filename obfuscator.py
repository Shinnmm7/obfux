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
    """Robustly recursively walk all nodes in the luaparser AST"""
    yield node
    # luaparser stores child nodes in standard attributes (like 'body', 'targets', 'args')
    for attr_name, attr_value in vars(node).items():
        if isinstance(attr_value, astnodes.Node):
            yield from walk_tree(attr_value)
        elif isinstance(attr_value, list):
            for item in attr_value:
                if isinstance(item, astnodes.Node):
                    yield from walk_tree(item)

def obfuscate(source: str, strength: str = "strong") -> str:
    cfg = STRENGTH_LEVELS.get(strength, STRENGTH_LEVELS["strong"])
    
    try:
        tree = ast.parse(source)
    except Exception as e:
        raise ValueError(f"Lua syntax error: {e}")

    # --- Pass 1: Variable & Argument Renaming ---
    if cfg["rename"]:
        var_map = {}
        
        # First pass: collect all local variable and argument names
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
        
        # Second pass: rename all references
        for node in walk_tree(tree):
            if isinstance(node, astnodes.Name):
                if node.id in var_map:
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

    # --- Pass 2: Junk Code Insertion ---
    if cfg["junk"]:
        for node in walk_tree(tree):
            if isinstance(node, astnodes.Block) and len(node.body) > 0:
                if random.random() < 0.3:
                    junk_var = rand_name()
                    junk_val = random.randint(1000, 99999)
                    try:
                        junk_code = ast.parse(f"local {junk_var} = {junk_val}")
                        if junk_code.body and isinstance(junk_code.body, list) and len(junk_code.body) > 0:
                            insert_pos = random.randint(0, len(node.body))
                            node.body.insert(insert_pos, junk_code.body[0])
                    except Exception:
                        pass  # Safely skip if junk insertion fails for any reason

    result = ast.to_lua_source(tree)

    # --- Pass 3: Control Flow Wrapping ---
    if cfg["wrap"]:
        result = f"do\n    local __state = {random.randint(1, 999)}\n    {result}\nend"

    return result
