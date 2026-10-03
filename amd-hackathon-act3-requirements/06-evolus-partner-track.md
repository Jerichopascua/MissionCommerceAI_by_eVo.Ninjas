# 06 — Evolus Partner Track (Optional): Business Agents on AMD

Build an AI agent that runs a **real business process end to end** on Evolus, powered by an **open model served on AMD**.

Agent flow: **input** (email, PDF, recording, web form, chat) → **reason** with open model on AMD → **act** (run Evolus workflow, docs → data, AI Tools, update another system, or hand off to a human).

## Requirements

- [ ] Build in a **free Evolus event workspace** at app.evolus.ai using the **event code shared at kickoff**
- [ ] **Bring your own model:** main agent uses an open model served on AMD via **your own vLLM endpoint on AMD Developer Cloud**
- [ ] Use **at least two** Evolus building blocks: workflows, document extractors, AI Tools, knowledge libraries, MCP connectors, sub-agents, chat widget
- [ ] **Drive Evolus from your app through its APIs** (REST API; agent chat via REST or OpenAI-compatible endpoint)
- [ ] Containerized app, public GitHub repo, a README that runs; **never commit API keys**

Verification: Evolus reviews each workspace's config + usage stats (connected model endpoint, building blocks used, API calls).

## Sample use cases (commerce-relevant ones bolded)

| Use case | Input | What it does |
|---|---|---|
| **Invoice & order intake** | Emails with PDFs | Extract fields to JSON, match to order, flag mismatches to a person |
| **Support desk on company knowledge** | Chat / email / widget | Answers from company docs with sources; escalates when unsure |
| **Lead qualification** | Website chat widget | Qualifies visitor, books a call, pushes lead to CRM via MCP |
| Contract review | Uploaded contracts | Extracts clauses, compares to standard terms, redacts PII |
| Multilingual documents | PDF / Word | Translates keeping layout, files via workflow |
| Meeting follow-up | Call recordings | Minutes + action items sent to attendees |

## Judging (Evolus lens)

- **Application of Technology:** depth of Evolus building blocks + quality of AMD-hosted model integration
- **Business Value:** real process, clear user, measurable gain
- **Originality:** new approach / process nobody automated this way
- **Presentation:** clear demo and pitch

## Evolus building blocks & APIs

| Block | Description | API |
|---|---|---|
| Agents & sub-agents | Tools + memory, on team's own model | REST `ask`, `ask-stream`; OpenAI-compatible `/v1/chat/completions` |
| Workflows | Multi-step pipelines (agents, doc reading, extractors, webhooks; branches/loops/parallel). Triggered by API, email, or schedule; result to callback URL | `POST /api/v1/workflows/{id}/execute` + execution status |
| Document extractors | PDFs/scans/images → JSON per your schema | REST or workflow step |
| AI Tools (11) | Doc→JSON/CSV/XML, tables, layout-preserving translation, PDF redaction, summaries, meeting minutes, email writing, rewriting, simplification, sentiment, text comparison | `/api/v1/ai-tools/{tool}/run`, `run-media`, `run-file` |
| Knowledge libraries (RAG) | Upload docs / import web pages; answers with sources | REST, attached to agents |
| Webhooks | Notify own systems | REST |
| MCP connectors | Connect agents to external systems (incl. our own MCP servers) | Workspace config |
| Chat widget | Agent on any website | One script tag |
| Evolus MCP server | Build/manage agents from Claude Code, Cursor, any MCP client | `https://api.evolus.ai/mcp` |
| Evolus Studio | Coding agent (OpenCode-based) with Evolus MCP built in | Desktop + CLI |

### Endpoints & auth

- REST: `https://api.evolus.ai/api/v1` — headers `X-ApiKey`, `X-Application-Id`
- OpenAI-compatible chat: base URL `https://api.evolus.ai/v1`, model `<applicationId>:<agentId>`, Bearer API key
- MCP: `https://api.evolus.ai/mcp` — same headers as REST
- Docs: evolus.ai/developers (quickstart before kickoff); interactive API reference inside each workspace

### Access (free)

- Sign in at app.evolus.ai (GitHub / Google / Apple / Microsoft)
- Enter event code → free workspace **until Oct 31, 2026**, up to **6 members**, **50,000 credits**, no card
- Doc reading, AI Tools, knowledge indexing consume workspace credits
