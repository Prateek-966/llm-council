# LLM Council

![llmcouncil](header.jpg)

A replica of [karpathy/llm-council](https://github.com/karpathy/llm-council), running current
model versions and seating the top open-weight models (DeepSeek, Qwen, Kimi) next to the frontier
ones, with Claude Opus 5 in the chair.

The idea of this repo is that instead of asking a question to your favorite LLM provider (e.g. OpenAI GPT-5.6 Sol, Anthropic Claude Opus 5, Google Gemini 3.7 Flash, xAI Grok 4.6, DeepSeek, Qwen, Kimi), you can group them into your "LLM Council". This repo is a simple, local web app that essentially looks like ChatGPT except it uses OpenRouter to send your query to multiple LLMs, it then asks them to review and rank each other's work, and finally a Chairman LLM produces the final response.

In a bit more detail, here is what happens when you submit a query:

1. **Stage 1: First opinions**. The user query is given to all LLMs individually, and the responses are collected. The individual responses are shown in a "tab view", so that the user can inspect them all one by one.
2. **Stage 2: Review**. Each individual LLM is given the responses of the other LLMs. Under the hood, the LLM identities are anonymized so that the LLM can't play favorites when judging their outputs. The LLM is asked to rank them in accuracy and insight.
3. **Stage 3: Final response**. The designated Chairman of the LLM Council takes all of the model's responses and compiles them into a single final answer that is presented to the user.

## Vibe Code Alert

This project was 99% vibe coded as a fun Saturday hack because I wanted to explore and evaluate a number of LLMs side by side in the process of [reading books together with LLMs](https://x.com/karpathy/status/1990577951671509438). It's nice and useful to see multiple responses side by side, and also the cross-opinions of all LLMs on each other's outputs. I'm not going to support it in any way, it's provided here as is for other people's inspiration and I don't intend to improve it. Code is ephemeral now and libraries are over, ask your LLM to change it in whatever way you like.

## Setup

### 1. Install Dependencies

The project uses [uv](https://docs.astral.sh/uv/) for project management.

**Backend:**
```bash
uv sync
```

**Frontend:**
```bash
cd frontend
npm install
cd ..
```

### 2. Configure API Key

Create a `.env` file in the project root:

```bash
OPENROUTER_API_KEY=sk-or-v1-...
```

Get your API key at [openrouter.ai](https://openrouter.ai/). Make sure to purchase the credits you need, or sign up for automatic top up.

### 3. Configure Models (Optional)

The council has seven members - four frontier models and the three leading open-weight ones -
and Claude Opus 5 chairs:

```python
COUNCIL_MODELS = [
    "openai/gpt-5.6-sol",
    "anthropic/claude-opus-5",
    "google/gemini-3.7-flash",
    "x-ai/grok-4.6",
    "deepseek/deepseek-v4-flash-0731",
    "qwen/qwen3.7-max",
    "moonshotai/kimi-k3",
]

CHAIRMAN_MODEL = "anthropic/claude-opus-5"
```

Claude sits on the council *and* chairs it, which is how upstream ran it (with Gemini). It
reviews its own Stage 1 answer in Stage 2, though anonymization means it doesn't know which one
is its own.

Edit `backend/config.py` to change the roster, or override from `.env` without touching the code.
Short aliases and full OpenRouter model ids both work:

| Alias | Resolves to |
| --- | --- |
| `gpt` | `openai/gpt-5.6-sol` |
| `claude` | `anthropic/claude-opus-5` |
| `claude-sonnet` | `anthropic/claude-sonnet-5` |
| `gemini` | `google/gemini-3.7-flash` |
| `gemini-pro` | `google/gemini-3.1-pro-preview` |
| `grok` | `x-ai/grok-4.6` |
| `deepseek` | `deepseek/deepseek-v4-flash-0731` |
| `deepseek-pro` | `deepseek/deepseek-v4-pro-0813` |
| `qwen` | `qwen/qwen3.7-max` |
| `kimi` | `moonshotai/kimi-k3` |

```bash
COUNCIL_MODELS=deepseek,qwen,kimi           # an all-open-weights council
CHAIRMAN_MODEL=claude-sonnet                # cheaper synthesis
TITLE_MODEL=google/gemini-3.7-flash         # small model that names conversations
```

Every call goes through OpenRouter, so any model in their catalog can join - see
[openrouter.ai/models](https://openrouter.ai/models). Two things to keep in mind:

- **Slugs go stale fast.** Labs ship new versions every few weeks and retire old ones. If a member
  silently stops contributing, check its id against the live catalog first - a bad slug is caught
  and logged in `query_model`, and that member is just dropped from the round.
- **Cost scales worse than linearly with council size.** Each member answers in Stage 1 *and*
  reviews every other member's answer in Stage 2, so the Stage 2 prompt grows with the roster.
  Swap in cheaper tiers (`gemini`, `deepseek`, `claude-sonnet`) or trim `COUNCIL_MODELS` if a
  round costs more than it's worth to you.

### 4. Running it for free (Optional)

Two ways to pay nothing.

**a) Free models on OpenRouter.** Model ids ending in `:free` cost $0. Still needs an OpenRouter
account, but no card and no credits:

```bash
COUNCIL_MODELS=<model-a>:free,<model-b>:free,<model-c>:free
CHAIRMAN_MODEL=<model-a>:free
TITLE_MODEL=<model-a>:free
```

The free roster rotates monthly, so pick current ids from
[openrouter.ai/collections/free-models](https://openrouter.ai/collections/free-models). The catch is
throughput: 20 requests/minute, and 50 requests/day at a $0 balance (1000/day once you have ever
bought $10 in credits). One council round with N members costs 2N+2 requests - so a 3-member
council is 8 requests, about six rounds/day on the free floor. Failed calls count against the quota
too.

**b) Local models, no API at all.** The backend talks plain OpenAI-compatible chat-completions, so
any local runtime works. With [Ollama](https://ollama.com):

```bash
ollama pull qwen3:8b && ollama pull llama3.1:8b && ollama pull deepseek-r1:8b
```

```bash
# .env
OPENROUTER_API_URL=http://localhost:11434/v1/chat/completions
OPENROUTER_API_KEY=
COUNCIL_MODELS=qwen3:8b,llama3.1:8b,deepseek-r1:8b
CHAIRMAN_MODEL=qwen3:8b
TITLE_MODEL=llama3.1:8b
```

Unlimited, offline, no account. The trade is quality and speed - these are small local models, not
the frontier ones, and Ollama runs them one at a time, so the council's parallel stages become
sequential. Note that council members here are *local* model tags (`qwen3:8b`), not OpenRouter
slugs (`qwen/qwen3.7-max`), and the aliases in `config.py` don't apply.

## Running the Application

**Option 1: Use the start script**
```bash
./start.sh
```

**Option 2: Run manually**

Terminal 1 (Backend):
```bash
uv run python -m backend.main
```

Terminal 2 (Frontend):
```bash
cd frontend
npm run dev
```

Then open http://localhost:5173 in your browser.

## Deploying to Render

`render.yaml` is a blueprint for both services on Render's free tier: the frontend as a static
site, the backend as a Python web service. Point Render at this repo (New > Blueprint), then set
`OPENROUTER_API_KEY` on the backend service - `ALLOWED_ORIGINS` and `VITE_API_URL` are wired
between the two services automatically.

Three things about the free tier that shape what you get:

- **The backend sleeps.** Free web services spin down after 15 minutes of inactivity; the next
  request takes 30-60 seconds to wake it. The first question after a quiet spell will feel broken
  but isn't. 750 instance-hours/month across the workspace.
- **Conversation history is not durable.** The free filesystem is ephemeral, so everything under
  `data/` is wiped on every redeploy, restart and spin-down. Chats are effectively single-session.
  A persistent disk is a paid add-on; a free Postgres (1 GB, expires 30 days after creation) plus a rewrite
  of `storage.py` is the free workaround.
- **Nothing here runs a model.** 512 MB RAM and 0.1 CPU cannot host an LLM, so the inference still
  happens somewhere else - OpenRouter, or a machine you control (see below).

## Tech Stack

- **Backend:** FastAPI (Python 3.10+), async httpx, OpenRouter API
- **Frontend:** React + Vite, react-markdown for rendering
- **Storage:** JSON files in `data/conversations/`
- **Package Management:** uv for Python, npm for JavaScript
