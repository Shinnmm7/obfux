<!-- coderabbit-ai-generated:v1 -->

# Nebula Obfuscator

Obfuscate Lua source through the web form or the Discord `/obf` command. Install dependencies with `python -m pip install -r requirements.txt`, then run `python -m uvicorn main:app`. Set `BOT_TOKEN` to enable the Discord bot.

## Modes

- **Light** removes comments and unnecessary whitespace using Lua tokens.
- **Medium** encodes the cleaned source in randomized chunks.
- **Strong** uses smaller, shuffled encoded chunks to make the output harder to inspect.

Medium and strong decode and compile the source at runtime and require Lua `load` or `loadstring`, as well as the standard string and table libraries. They cannot run in environments that disable dynamic loading. Lua 5.1, 5.2, 5.3 and 5.4 are covered by the execution tests. Input must be accepted by the installed `luaparser`; dialect-specific syntax may not be supported.

Obfuscation does not provide cryptographic secrecy: anyone who controls the runtime can intercept or recover the decoded source. Keep credentials and other secrets on a trusted server.

Run the tests with `python -m unittest discover -s tests -v`. The execution tests require Lua interpreters on PATH.
