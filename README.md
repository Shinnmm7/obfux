<!-- coderabbit-ai-generated:v1 -->

# Nebula Obfuscator

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:3f04a7ff46f4415ced7bc7d2b1511f2ae7f906d07365ad91357692192f242d72 -->

Obfuscate Lua source through the web form or the Discord `/obf` command. Install dependencies with `python -m pip install -r requirements.txt`, then run `python -m uvicorn main:app`. Set `BOT_TOKEN` to enable the Discord bot.

## Deploy on Railway

The root `Dockerfile` installs Python dependencies plus Lua 5.1 and OpenSSL, which Roblox mode needs. Railway detects this Dockerfile when it builds the repository. Python dependency installation alone does not install these OS tools.

1. Merge the deployment fix into the branch connected to your Railway service, or deploy the task branch.
2. Keep your existing `BOT_TOKEN` in Railway's service variables. Do not add it to the Dockerfile or repository.
3. Clear a custom Start Command to use the Dockerfile's default, or use `sh -c 'exec python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}'`. A command that only runs `python main.py` does not start this application.
4. Redeploy and confirm the build log says `Using detected Dockerfile!`. Retry `/obf` after the bot reconnects.

The container starts the website and Discord bot in one Uvicorn worker and binds Railway's `PORT` (8000 locally). For a local container: `docker build -t nebula-obfuscator .`, then `docker run --rm -p 8000:8000 --env BOT_TOKEN nebula-obfuscator`. Set `BOT_TOKEN` in your shell first if you want the bot; omit `--env BOT_TOKEN` for website-only testing.

On an existing Debian/Ubuntu host without Docker, install `lua5.1` and `openssl` using the OS package manager, then restart the application. See [Railway Dockerfile detection](https://docs.railway.com/builds/dockerfiles) and [start-command configuration](https://docs.railway.com/builds/build-and-start-commands).


<!-- /coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:ea14eb8091769e7d3a0cbfba699032f8c465367c61c8f72a608cec57aec7a5a6 -->

## Modes

- **Light** removes comments and unnecessary whitespace using Lua tokens.
- **Medium** encodes the cleaned source in randomized chunks.
- **Strong** uses smaller, shuffled encoded chunks to make the output harder to inspect.
<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:483f991bbbec1b36226f4128561f30c7a74929efc8a2e6a8bfd52f2d0f106bf1 -->

- **Roblox Luau** uses a VM-based transform and string and control-flow obfuscation. It is the default for the web form, API uploads with no strength field, and Discord `/obf`. Use it for Roblox LocalScripts. Files previously produced by Medium or Strong must be regenerated in Roblox mode. The Python `obfuscate()` library default remains `strong` for existing Lua callers.

<!-- /coderabbit-ai-generated:v1 -->

Medium and strong decode and compile the source at runtime and require Lua `load` or `loadstring`, as well as the standard string and table libraries. They cannot run in environments that disable dynamic loading. Lua 5.1, 5.2, 5.3 and 5.4 are covered by the execution tests. Input must be accepted by the installed `luaparser`; dialect-specific syntax may not be supported.

Roblox mode requires `lua5.1` and `openssl` on the server's PATH. It accepts up to 64 KiB of UTF-8 source and supports only a subset of Luau: type annotations, type declarations and interpolated strings are unsupported. It changes debug information and may change behavior for code that replaces a running function's environment. See [Prometheus limitations](https://github.com/prometheus-lua/Prometheus/blob/a98c50165f2a53f6d765a82eee60dfea53803445/doc/reference/limitations.md). Generated code can be much larger and slower; test it in your Roblox environment. There is no guarantee of Luraph-equivalent protection or resistance to deobfuscation.

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:e65e9dd19e84ac43e9bd0f9bb789de3cd0f81c69a2a56f879afe0d5eae2c52d4 -->

### VM storage protections

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:8608b28e8fd4edc3cf158d0318cf6d1517d593f0462c8bbc7b9891b3aebfb342 -->

Roblox mode stores instructions and constants as individually keyed records. The VM verifies and decodes each record on demand and does not retain a decoded instruction or constant cache. The startup tables contain encoded records; values needed by the running script still exist in its registers and application objects.

Each build chooses new value tags and decoder parameters. Each record has a random nonce and uses the preceding ciphertext byte when updating its decoding state. Instructions are stored at addresses derived from their logical position, prototype key and build parameters rather than in a sequential code array. These changes vary the record representation across builds and make a fixed-format decoder insufficient; they do not prevent an analyst from extracting the generated schema or tracing execution. Older generated scripts remain self-contained and need no migration.

<!-- /coderabbit-ai-generated:v1 -->

Record checksums reject corrupted payloads before use. They are not cryptographic authentication, and the reversible encoding is not cryptographic encryption. Keys and the decoder ship with the program. Someone controlling the runtime can instrument decoding, recover values or patch the checks. Clearing references permits garbage collection; it does not securely erase memory. These changes reduce exposure to simple startup table dumps and do not establish Luraph-equivalent or general anti-dumping protection.

Based on Prometheus by Elias Oelschner, https://github.com/prometheus-lua/Prometheus. This project modifies its VM data, layout, runtime and dispatch modules and adds a record codec. The upstream revision, local changes and license are recorded in `vendor/prometheus/`.

<!-- /coderabbit-ai-generated:v1 -->

<!-- /coderabbit-ai-generated:v1 -->

Obfuscation does not provide cryptographic secrecy: anyone who controls the runtime can intercept or recover the decoded source. Keep credentials and other secrets on a trusted server.

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:4e7e8edf57179fb7e6bb39c028f006c99df43321ddbcc5112a88d23dbf6d644c -->

Run the tests with `python -m unittest discover -s tests -v`. The Lua execution tests require Lua interpreters on PATH. To run the Roblox execution test, install the Luau CLI on PATH or set `LUAU_BIN` to its executable; the compiler tests also require `lua5.1` and `openssl`.

<!-- /coderabbit-ai-generated:v1 -->
