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

def obfuscate(source: str, strength: str = "strong") -> str:
    cfg = STRENGTH_LEVELS.get(strength, STRENGTH_LEVELS["strong"])
    
    try:
        tree = ast.parse(source)
    except Exception as e:
        raise ValueError(f"Lua syntax error: {e}")

    # --- Pass 1: Variable & Argument Renaming ---
    var_map = {}
    class Renamer(ast.ASTVisitor):
        def visit_LocalAssign(self, node):
            for t in node.targets:
                if isinstance(t, astnodes.Name) and t.id not in var_map:
                    var_map[t.id] = rand_name()
                if isinstance(t, astnodes.Name):
                    t.id = var_map[t.id]
            self.visit_children(node)
            
        def visit_Name(self, node):
            if node.id in var_map:
                node.id = var_map[node.id]
            self.visit_children(node)
            
        def visit_Function(self, node):
            for arg in node.args:
                if isinstance(arg, astnodes.Name) and arg.id not in var_map:
                    var_map[arg.id] = rand_name()
                if isinstance(arg, astnodes.Name):
                    arg.id = var_map[arg.id]
            self.visit_children(node)

    Renamer().visit(tree)

    # --- Pass 2: Junk Code Insertion ---
    if cfg["junk"]:
        class JunkInserter(ast.ASTVisitor):
            def visit_Block(self, node):
                self.visit_children(node)
                if random.random() < 0.4 and len(node.body) > 0:
                    junk_var = rand_name()
                    junk_val = random.randint(1000, 99999)
                    junk_code = ast.parse(f"local {junk_var} = {junk_val}")
                    node.body.insert(random.randint(0, len(node.body)), junk_code.body[0])
        JunkInserter().visit(tree)

    result = ast.to_lua_source(tree)

    # --- Pass 3: Basic Control Flow Wrapping ---
    if cfg["wrap"]:
        result = f"do\n    local __state = {random.randint(1, 999)}\n    {result}\nend"

    return result
