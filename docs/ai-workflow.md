# AI-assisted reverse engineering workflow

This project uses LLM agents to speed up the tedious parts of reverse engineering. Humans check every claim
against real hardware before it goes into the docs.

## Tools

| Tool | Use |
|---|---|
| [REA (Reverse Engineer Anything)](https://www.noze.it/en/insights/rea-reverse-engineer-anything-with-agents/) | MCP server: APK, native binaries, firmware triage (`npx rea-agents setup`). Firmware extraction needs Binwalk/Unblob, so use WSL on Windows |
| [GhidraMCP](https://github.com/LaurieWired/GhidraMCP) | Lets the agent drive Ghidra: decompile, rename, follow cross-references |
| ReVa | Ghidra extension, model-agnostic assistant over MCP |
| jadx | Decompile the Linklemo APK and its native libraries |
| Wireshark | Capture app ↔ camera traffic |

## Rules

- Analysis runs **locally**. Do not upload firmware dumps or captures to third-party services.
- Never commit device secrets, prekeys or vendor binaries (see `.gitignore`).
- Mark AI-derived findings as _unverified_ until they are confirmed on a real camera.
