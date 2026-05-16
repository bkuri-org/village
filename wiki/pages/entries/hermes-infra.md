---
id: hermes-infra
tags: [infrastructure, cross-project, homelab, reference]
created: 2026-05-13T14:57:00.000000+00:00
source: cross-project-inventory
---

# Hermes Infrastructure Knowledge Base

Cross-project infrastructure reference for the Hermes agent homelab. Covers all
active projects, shared services, networking, automation, and operational
conventions.

---

## Projects Overview

| Project | Path | Repo | Description |
|---------|------|------|-------------|
| **MCProxy** | `/home/hermes/projects/mcproxy` | `bkuri/mcproxy` | MCP gateway aggregating stdio/HTTP MCP servers (v5.1.0, Python 3.11+, port 12010) |
| **Village** | `/home/hermes/projects/village` | `bkuri-org/village` | Parallel development OS for AI agents — task store, scribe, tmux orchestration |
| **GridPower** | `/home/hermes/projects/GridPower` | `bkuri-org/GridPower` | Democratic infrastructure PDK — Solidity contracts + JS SDK, three-chain architecture |
| **Scripts** | `/home/hermes/projects/scripts` | — | Operational automation: daily-pulse, ntfy-dispatch |
| **Jesse MCP** | (remote) | `bkuri-org/jesse-mcp` | MCP server for Jesse trading bot |
| **Maxitrader** | (remote) | `bkuri-org/maxitrader` | Crypto trading system |
| **Hermes LLM Wiki Memory** | `/home/hermes/projects/hermes-llm-wiki-memory` | `bkuri-org/hermes-llm-wiki-memory` | Karpathy-style LLM wiki as a Hermes memory adapter (Python) |
| **PPC** | (remote) | `bkuri-org/ppc` | Project management / coordination |

---

## Network Topology

### Core Services

| Service | Address | Notes |
|---------|---------|-------|
| **MCProxy** | `http://192.168.50.71:12010` | MCP gateway, SSE endpoints |
| **Jesse Trading** | `http://localhost:9100` | Jesse trading bot API |
| **Jesse MCP Bridge** | `http://localhost:12011/mcp` | HTTP MCP server bridging to Jesse |
| **Home Assistant** | `http://192.168.50.99:8099` | Smart home agent API |
| **ntfy (notifications)** | `https://ntfy.lan` | Self-hosted notification relay |
| **Zilliqa Insights** | `https://insights.mcp.zilliqa.com/mcp` | Remote blockchain MCP server |

### MCP Server Endpoints

MCProxy exposes namespaced SSE endpoints:

| Endpoint | Namespace | Servers |
|----------|-----------|---------|
| `/sse` | default | All non-isolated servers |
| `/sse/docs` | docs | wikipedia, llms_txt |
| `/sse/trading` | trading | jesse (isolated) |
| `/sse/home` | home | home_assistant |
| `/sse/automation` | automation | tmux, playwright |

---

## MCProxy Configuration

### Registered MCP Servers (17 total)

**Thinking & Reasoning:**
- `sequential_thinking` — Structured chain-of-thought
- `atom_of_thoughts` — Decomposition reasoning
- `think_tool` — Simple thinking aid

**Financial & Market Data:**
- `fear_greed_index` — Market sentiment
- `coinstats` — Crypto stats (API key: `COINSTATS_API_KEY`)
- `asset_price` — Real-time asset prices
- `coinmarketcap` — CMC data (API key: `CMC_API_KEY`, uses `/srv/containers/mcproxy/venv`)
- `jesse` — Trading bot (HTTP, `localhost:12011/mcp`, extended timeouts for backtest/optimize/walk_forward)

**Documentation & Research:**
- `llms_txt` — LangGraph docs via `mcpdoc`
- `wikipedia` — Wikipedia search
- `youtube` — YouTube transcript access
- `pure_md` — Markdown extraction (API key: `PUREMD_API_KEY`)
- `perplexity_sonar` — Perplexity AI search (API key: `PERPLEXITY_API_KEY`, model: sonar)

**Automation:**
- `tmux` — Terminal multiplexer control
- `playwright` — Browser automation

**IoT & Home:**
- `home_assistant` — Smart home control (HA agent at `192.168.50.99:8099`)

**Blockchain:**
- `zilliqa_insights` — Zilliqa blockchain analytics (remote HTTP)

### Namespace Groups

| Group | Namespaces | Use Case |
|-------|-----------|----------|
| `dev` | thinking, docs | Development work |
| `dev_full` | thinking, docs, web | Dev with web access |
| `research` | thinking, docs, web, financial, blockchain | Full research |
| `automation_full` | automation, web | Browser automation |
| `everything` | All except trading | General-purpose agent |
| `maxitrader` | thinking, financial, docs, web, blockchain + !trading | Trading research |
| `normal` | automation, docs, home, thinking, web | Daily operations |

### Sandbox Configuration

- **Timeout:** 900s (15 min)
- **Pool size:** 3 (max 10)
- **Idle timeout:** 300s (5 min)

---

## Automation Pipeline

### Daily Pulse (`scripts/daily-pulse.py`)

Runs daily to collect cross-project activity:
1. Queries GitHub API for commits (last 24h) and open PRs
2. Reads local beads issues (`open`/`closed`, by type/priority)
3. Counts scribe wiki notes per project
4. Posts per-project summaries to `ntfy.lan/org`
5. Escalates critical beads issues (priority 0)

### ntfy Dispatcher (`scripts/ntfy-dispatch.py`)

Polls `ntfy.lan/org` and dispatches actions based on priority:
- **p5 (critical):** Immediate Telegram + system escalation
- **p4 + project tag:** Project-specific action (alert to Matrix room or trigger `village builder`)
- **<p4:** Informational only, skipped

**Project dispatch actions:**
| Project | Action | Target |
|---------|--------|--------|
| maxitrader | alert | Matrix `!lKTnXGmRtpCSIUtZYe:bkuri.lan` + TG topic |
| jesse-mcp | alert | Matrix `!BBDeLMiTDGZbFgPmTu:bkuri.lan` |
| mcproxy | alert | Matrix `!FjhGvCwsLDJRpKYLZm:bkuri.lan` |
| village | **build** | Triggers `village builder run` |
| hermes-llm-wiki-memory | alert | Matrix `!EqJuHXnvMdfZxhvRuA:bkuri.lan` |
| GridPower | alert | Matrix `!lXjMaHRhjlcpwYpVlP:bkuri.lan` |
| ppc | alert | Matrix `!AfvwxCQRdoSwatOcaY:bkuri.lan` |

---

## Task Tracking (Beads)

All projects use **bd (beads)** for issue tracking:
- Issues stored in local embedded Dolt DB (`.beads/`)
- Synced via `refs/dolt/data` on git remote
- `.beads/issues.jsonl` is a passive export
- Priority scale: 0 (critical) → 4 (backlog)
- Statuses: `open`, `draft`, `in_progress`, `done`, `closed`, `deferred`

---

## Environment Variables

Keys referenced across the infrastructure (never commit values):

| Variable | Used By |
|----------|---------|
| `COINSTATS_API_KEY` | MCProxy → coinstats server |
| `CMC_API_KEY` | MCProxy → coinmarketcap server |
| `PUREMD_API_KEY` | MCProxy → pure_md server |
| `PERPLEXITY_API_KEY` | MCProxy → perplexity_sonar + jesse LLM endpoint |
| `MCPROXY_ADMIN_KEY` | MCProxy admin API auth |

---

## GridPower Specifics

- **Architecture:** Three-chain blockchain (identity, voting, location attestation)
- **Tech Stack:** Solidity ^0.8.19, Hardhat, Ethers.js, ZK PLONK proofs
- **Monorepo:** `packages/contracts` (Solidity), `packages/sdk` (JS), `packages/integration-tests`
- **CI Thresholds:** ≥85% line coverage, ≥80% branch coverage
- **MVP Status:** Core complete, real PLONK proofs verified on-chain, 239 tests passing

---

## Village Specifics

- **Role:** Orchestration layer for parallel AI agent development
- **Components:** Task store, Scribe (wiki), Builder (spec-driven build loop), Watcher
- **Wiki:** 17 entries at `wiki/pages/entries/` (this document is #18)
- **Templates:** single-service, multi-service configurations available
- **Issue tracking:** Internal `bd` for Village's own development; `village tasks` for managed projects

---

## Operational Conventions

1. **All work tracked via beads** — no markdown TODOs, no external trackers
2. **Session completion requires `git push`** — work is not done until pushed
3. **ntfy is the central nervous system** — all notifications route through `ntfy.lan`
4. **Matrix rooms per project** — each project has a dedicated Matrix channel for alerts
5. **MCProxy is the tool gateway** — all MCP tooling routes through the proxy
6. **Bump labels mandatory** — every closed task needs `bump:major/minor/patch/none`
7. **Plain text, JSON contracts** — no hidden state, everything inspectable
8. **Spec-driven development** — Village builder uses specs to drive autonomous build loops

---

*Auto-generated from cross-project inventory. Last updated: 2026-05-13.*
