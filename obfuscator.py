import random
import string
import re
from luaparser import ast, astnodes

STRENGTH_LEVELS = {
    "light":   {"rename": True, "strings": False, "junk": False, "cflow": False, "minify": False},
    "medium":  {"rename": True, "strings": True, "junk": False, "cflow": False, "minify": True},
    "strong":  {"rename": True, "strings": True, "junk": True, "opaque": True, "cflow": True, "minify": True},
}

def rand_name(length=2):
    # Luraph-style short variable names
    return "".join(random.choices(string.ascii_letters, k=length))

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

def minify_lua(code: str) -> str:
    """Compress Lua code into a dense, unreadable format"""
    # 1. Remove all comments
    code = re.sub(r'--\[\[.*?\]\]', '', code, flags=re.DOTALL)
    code = re.sub(r'--[^\n]*', '', code)
    
    # 2. Replace newlines with spaces
    code = code.replace('\n', ' ')
    
    # 3. Collapse multiple spaces
    code = re.sub(r' +', ' ', code)
    
    # 4. Prevent keyword merging (e.g., "endif" -> "end if")
    keywords = ['end', 'local', 'function', 'return', 'elseif', 'else', 'while', 'do', 'if', 'for', 'in', 'not', 'and', 'or', 'then', 'repeat', 'until', 'break']
    for kw in keywords:
        code = re.sub(rf'(?<!\w){kw}(?=\w)', rf'{kw} ', code)
        code = re.sub(rf'(?<=\w){kw}(?!\w)', rf' {kw}', code)
        
    # 5. Remove spaces around operators and punctuation
    code = re.sub(r'\s*([=,;{}\(\)\+\-\*\/\^\<\>\~\#])\s*', r'\1', code)
    
    return code.strip()

def obfuscate(source: str, strength: str = "strong") -> str:
    cfg = STRENGTH_LEVELS.get(strength, STRENGTH_LEVELS["strong"])
    
    try:
        tree = ast.parse(source)
    except Exception as e:
        raise ValueError(f"Lua syntax error: {e}")

    # ==========================================
    # PASS 1: Variable Renaming (Short 1-2 char names)
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

    current_source = ast.to_lua_source(tree)
    
    try:
        tree = ast.parse(current_source)
    except Exception:
        pass

    # ==========================================
    # PASS 2: String Encryption
    # ==========================================
    if cfg["strings"]:
        strings_to_encrypt = []
        for node in walk_tree(tree):
            if isinstance(node, astnodes.String) and node.start_char is not None:
                strings_to_encrypt.append(node)
        
        strings_to_encrypt.sort(key=lambda n: n.start_char, reverse=True)
        
        if strings_to_encrypt:
            global_key = rand_name(4)
            for node in strings_to_encrypt:
                encrypted_bytes = xor_encrypt_bytes(node.s, global_key)
                byte_array = "{" + ",".join(map(str, encrypted_bytes)) + "}"
                replacement = f'__D({byte_array},"{global_key}")'
                current_source = current_source[:node.start_char] + replacement + current_source[node.stop_char+1:]

    # ==========================================
    # PASS 3: Control Flow Flattening (Dense State Machine)
    # ==========================================
    if cfg["cflow"]:
        lines = [line.strip() for line in current_source.split('\n') if line.strip()]
        if len(lines) > 8:
            chunk_size = max(1, len(lines) // 4)
            chunks = []
            for i in range(0, len(lines), chunk_size):
                chunks.append(' '.join(lines[i:i+chunk_size]))
            
            if len(chunks) > 1:
                state_var = rand_name()
                s1, s2, s3 = rand_name(), rand_name(), rand_name()
                flattened = f"""
do local {state_var}=0 while true do if {state_var}==0 then {chunks[0]} {state_var}={s1} elseif {state_var}=={s1} then {chunks[1] if len(chunks)>1 else ''} {state_var}={s2} elseif {state_var}=={s2} then {chunks[2] if len(chunks)>2 else ''} {state_var}={s3} else {chunks[3] if len(chunks)>3 else ''} break end end end
"""
                current_source = flattened

    # ==========================================
    # PASS 4: Opaque Predicates & Junk
    # ==========================================
    if cfg["junk"] or cfg["opaque"]:
        fake_math1 = random.randint(1000, 9999)
        fake_math2 = random.randint(1000, 9999)
        opaque_check = f"do local __c=({fake_math1}*{fake_math2}) if __c~={fake_math1*fake_math2}+{random.randint(1,5)} then error('Tamper Detected') end end"
        current_source = opaque_check + " " + current_source

    # ==========================================
    # PASS 5: Runtime Decryption Function (Shortened)
    # ==========================================
    if cfg["strings"]:
        runtime_decryptor = "local function __D(b,k) local o={} local l=#k for i=1,#b do o[i]=string.char(b[i]~string.byte(k,((i-1)%l)+1)) end return table.concat(o) end"
        current_source = runtime_decryptor + " " + current_source

    # ==========================================
    # PASS 6: Minification
    # ==========================================
    if cfg["minify"]:
        current_source = minify_lua(current_source)
    
    # ==========================================
    # PASS 7: Custom ASCII Logo & Header
    # ==========================================
    # Added AFTER minification so the ASCII art stays perfectly formatted
    custom_header = """===================================================
  __   __  ___   ___  ____  ____  ____ 
 / /  / / / _ \\ / _ \\|  _ \\|  _ \\/ ___|
| |  | | | | | | | | | |_) | |_) \\___ \\
| |  | | | |_| | |_| |  _ <|  __/ ___) |
 \\_\\  \\_\\  \\___/ \\___/|_| \\_\\_|   |____/ 
      辛贤 混淆器 | 中文Lua保护（不强）
===================================================
"""
    
    return custom_header + current_source
