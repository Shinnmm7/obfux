<!-- coderabbit-ai-generated:v1 -->

# Nebula Obfuscator

Obfuscate Lua source through the web form or the Discord `/obf` command. Install dependencies with `python -m pip install -r requirements.txt`, then run `python -m uvicorn main:app`. Set `BOT_TOKEN` to enable the Discord bot.

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:ea14eb8091769e7d3a0cbfba699032f8c465367c61c8f72a608cec57aec7a5a6 -->

## Modes

- **Light** removes comments and unnecessary whitespace using Lua tokens.
- **Medium** encodes the cleaned source in randomized chunks.
- **Strong** uses smaller, shuffled encoded chunks to make the output harder to inspect.
- **Roblox Luau** uses a VM-based transform and string and control-flow obfuscation. Select `roblox` in the web form or Discord `/obf` command.

Medium and strong decode and compile the source at runtime and require Lua `load` or `loadstring`, as well as the standard string and table libraries. They cannot run in environments that disable dynamic loading. Lua 5.1, 5.2, 5.3 and 5.4 are covered by the execution tests. Input must be accepted by the installed `luaparser`; dialect-specific syntax may not be supported.

Roblox mode requires `lua5.1` and `openssl` on the server's PATH. It accepts up to 64 KiB of UTF-8 source and supports only a subset of Luau: type annotations, type declarations and interpolated strings are unsupported. It changes debug information and may change behavior for code that replaces a running function's environment. See [Prometheus limitations](https://github.com/prometheus-lua/Prometheus/blob/a98c50165f2a53f6d765a82eee60dfea53803445/doc/reference/limitations.md). Generated code can be much larger and slower; test it in your Roblox environment. There is no guarantee of Luraph-equivalent protection or resistance to deobfuscation.

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:e65e9dd19e84ac43e9bd0f9bb789de3cd0f81c69a2a56f879afe0d5eae2c52d4 -->

### VM storage protections

Roblox mode stores instructions and constants as individually keyed records. The VM verifies and decodes each record on demand and does not retain a decoded instruction or constant cache. The startup tables contain encoded records; values needed by the running script still exist in its registers and application objects.

Record checksums reject corrupted payloads before use. They are not cryptographic authentication, and the reversible encoding is not cryptographic encryption. Keys and the decoder ship with the program. Someone controlling the runtime can instrument decoding, recover values or patch the checks. Clearing references permits garbage collection; it does not securely erase memory. These changes reduce exposure to simple startup table dumps and do not establish Luraph-equivalent or general anti-dumping protection.

Based on Prometheus by Elias Oelschner, https://github.com/prometheus-lua/Prometheus. This project modifies its VM data, layout, runtime and dispatch modules and adds a record codec. The upstream revision, local changes and license are recorded in `vendor/prometheus/`.

<!-- /coderabbit-ai-generated:v1 -->

<!-- /coderabbit-ai-generated:v1 -->

Obfuscation does not provide cryptographic secrecy: anyone who controls the runtime can intercept or recover the decoded source. Keep credentials and other secrets on a trusted server.

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:4e7e8edf57179fb7e6bb39c028f006c99df43321ddbcc5112a88d23dbf6d644c -->

Run the tests with `python -m unittest discover -s tests -v`. The Lua execution tests require Lua interpreters on PATH. To run the Roblox execution test, install the Luau CLI on PATH or set `LUAU_BIN` to its executable; the compiler tests also require `lua5.1` and `openssl`.

<!-- /coderabbit-ai-generated:v1 -->
