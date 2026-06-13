<a name="top"></a>
<div align="center">

<img src="https://capsule-render.vercel.app/api?type=rect&color=0:6b46c1,100:2b6cb0&height=120&section=header&text=RFSURVEY&fontSize=48&fontColor=ffffff&fontAlignY=58" width="100%" alt="RFSURVEY"/>

# RFSURVEY

### Analyze RF spectrum-occupancy CSV/metadata for band usage, interference, and anomalies.

<img src="https://readme-typing-svg.demolab.com?font=Fira+Code&size=18&duration=3500&pause=1000&color=6B46C1&center=true&vCenter=true&width=720&lines=Analyze+RF+spectrumoccupancy+CSVmetadata+for+band+usage+inte;Self-hostable+%C2%B7+MCP-native+%C2%B7+CI-ready+%C2%B7+polyglot" width="720"/>

[![PyPI](https://img.shields.io/pypi/v/cognis-rfsurvey.svg?color=6b46c1)](https://pypi.org/project/cognis-rfsurvey/) [![CI](https://github.com/cognis-digital/rfsurvey/actions/workflows/ci.yml/badge.svg)](https://github.com/cognis-digital/rfsurvey/actions) [![License: COCL 1.0](https://img.shields.io/badge/License-COCL%201.0-2b6cb0.svg)](LICENSE) [![Suite](https://img.shields.io/badge/Cognis-Neural%20Suite-6b46c1.svg)](https://github.com/cognis-digital)

*Part of the Cognis Neural Suite.*

</div>

```bash
pip install cognis-rfsurvey
rfsurvey scan .            # → prioritized findings in seconds
```

## Usage — step by step

1. **Install** (Python 3.9+):

   ```bash
   pip install rfsurvey            # or: pipx install rfsurvey
   ```

2. **Analyze a spectrum sweep.** Point `analyze` at a sweep CSV (or `-` for stdin):

   ```bash
   rfsurvey analyze sweep.csv
   ```

3. **Tune detection.** Set how many dB above the estimated noise floor counts as occupied (`--squelch-offset`, default 10), the z-score threshold for power-spike anomalies (`--z-thresh`, default 6.0), and the persistence minimum (`--persist-sweeps`, default 3):

   ```bash
   rfsurvey analyze sweep.csv --squelch-offset 8 --z-thresh 5 --format json > spectrum.json
   ```

4. **Read the result.** The report lists occupied bins, persistent emitters, and power-spike anomalies. JSON mode emits structured records suited to time-series monitoring.

5. **Gate in monitoring pipelines.** Use `--fail-on-anomaly` to exit non-zero whenever an anomaly is detected:

   ```bash
   rfsurvey analyze sweep.csv --fail-on-anomaly
   ```

## Contents

- [Why rfsurvey?](#why) · [Features](#features) · [Quick start](#quick-start) · [Example](#example) · [Architecture](#architecture) · [AI stack](#ai-stack) · [How it compares](#how-it-compares) · [Integrations](#integrations) · [Install anywhere](#install-anywhere) · [Related](#related) · [Contributing](#contributing)

<a name="why"></a>
## Why rfsurvey?

Analyze RF spectrum-occupancy CSV/metadata for band usage, interference, and anomalies. — without standing up heavyweight infrastructure.

`rfsurvey` is single-purpose, scriptable, and self-hostable: point it at a target, get prioritized results in the format your workflow already speaks (table · JSON · SARIF), gate CI on it, and let agents drive it over MCP.

<div align="right"><a href="#top">↑ back to top</a></div>

<a name="features"></a>
## Features

- ✅ Load Samples
- ✅ Estimate Noise Floor
- ✅ Summarize Bands
- ✅ Detect Anomalies
- ✅ Analyze
- ✅ Runs on Linux/macOS/Windows · Docker · devcontainer
- ✅ Ports in Python, JavaScript, Go, and Rust (`ports/`)

<div align="right"><a href="#top">↑ back to top</a></div>

<a name="quick-start"></a>
## Quick start

```bash
pip install cognis-rfsurvey
rfsurvey --version
rfsurvey scan .                       # scan current project
rfsurvey scan . --format json         # machine-readable
rfsurvey scan . --fail-on high        # CI gate (non-zero exit)
```

<div align="right"><a href="#top">↑ back to top</a></div>

<a name="example"></a>
## Example

```text
$ rfsurvey scan .
  [HIGH    ] RFS-001  example finding             (./src/app.py)
  [MEDIUM  ] RFS-002  another signal              (./config.yaml)

  2 findings · risk score 5 · 38ms
```

<div align="right"><a href="#top">↑ back to top</a></div>

<a name="architecture"></a>
## Architecture

```mermaid
flowchart LR
  IN[input] --> P[rfsurvey<br/>analyze + score]
  P --> OUT[report]
```

<div align="right"><a href="#top">↑ back to top</a></div>

<a name="ai-stack"></a>
## Use it from any AI stack

`rfsurvey` is interoperable with every popular way of using AI:

- **MCP server** — `rfsurvey mcp` (Claude Desktop, Cursor, Cognis.Studio, [uncensored-fleet](https://github.com/cognis-digital/uncensored-fleet))
- **OpenAI-compatible / JSON** — pipe `rfsurvey scan . --format json` into any agent or LLM
- **LangChain · CrewAI · AutoGen · LlamaIndex** — wrap the CLI/JSON as a tool in one line
- **CI / scripts** — exit codes + SARIF for non-AI pipelines

<div align="right"><a href="#top">↑ back to top</a></div>

<a name="how-it-compares"></a>
## How it compares

| | **Cognis rfsurvey** | typical tools |
|---|:---:|:---:|
| Self-hostable, no account | ✅ | varies |
| Single command, zero config | ✅ | ⚠️ |
| JSON + SARIF for CI | ✅ | varies |
| MCP-native (AI agents) | ✅ | ❌ |
| Polyglot ports (JS/Go/Rust) | ✅ | ❌ |
| Open license | ✅ COCL | varies |
<div align="right"><a href="#top">↑ back to top</a></div>

<a name="integrations"></a>
## Integrations

Pipes into your stack: **SARIF** for code-scanning, **JSON** for anything, an **MCP server** (`rfsurvey mcp`) for AI agents, and a webhook forwarder for SIEM/Slack/Jira. See [`docs/INTEGRATIONS.md`](docs/INTEGRATIONS.md).

<div align="right"><a href="#top">↑ back to top</a></div>

<a name="install-anywhere"></a>
## Install — every way, every platform

```bash
pip install "git+https://github.com/cognis-digital/rfsurvey.git"    # pip (works today)
pipx install "git+https://github.com/cognis-digital/rfsurvey.git"   # isolated CLI
uv tool install "git+https://github.com/cognis-digital/rfsurvey.git" # uv
pip install cognis-rfsurvey                                          # PyPI (when published)
docker run --rm ghcr.io/cognis-digital/rfsurvey:latest --help        # Docker
brew install cognis-digital/tap/rfsurvey                             # Homebrew tap
curl -fsSL https://raw.githubusercontent.com/cognis-digital/rfsurvey/main/install.sh | sh
```

| Linux | macOS | Windows | Docker | Cloud |
|---|---|---|---|---|
| `scripts/setup-linux.sh` | `scripts/setup-macos.sh` | `scripts/setup-windows.ps1` | `docker run ghcr.io/cognis-digital/rfsurvey` | [DEPLOY.md](docs/DEPLOY.md) (AWS/Azure/GCP/k8s) |

<div align="right"><a href="#top">↑ back to top</a></div>

<a name="related"></a>
## Related Cognis tools


**Explore the suite →** [🗂️ all 170+ tools](https://github.com/cognis-digital/cognis-neural-suite) · [⭐ awesome-cognis](https://github.com/cognis-digital/awesome-cognis) · [🔗 cognis-sources](https://github.com/cognis-digital/cognis-sources) · [🤖 uncensored-fleet](https://github.com/cognis-digital/uncensored-fleet) · [🧠 engram](https://github.com/cognis-digital/engram)

<div align="right"><a href="#top">↑ back to top</a></div>

<a name="contributing"></a>
## Contributing

PRs, new rules, and demo scenarios are welcome under the collaboration-pull model — see [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

> ### ⭐ If `rfsurvey` saved you time, **star it** — it genuinely helps others find it.

## Interoperability

`{}` composes with the 300+ tool Cognis suite — JSON in/out and a shared
OpenAI-compatible `/v1` backbone. See **[INTEROP.md](INTEROP.md)** for the
suite map, composition patterns, and reference stacks.

## License

Source-available under the **Cognis Open Collaboration License (COCL) v1.0** — free for personal, internal-evaluation, research, and educational use; **commercial / production use requires a license** (licensing@cognis.digital). See [LICENSE](LICENSE).

---

<div align="center"><sub><b><a href="https://cognis.digital">Cognis Digital</a></b> · one of 170+ tools in the <a href="https://github.com/cognis-digital/cognis-neural-suite">Cognis Neural Suite</a> · <i>Making Tomorrow Better Today</i></sub></div>
