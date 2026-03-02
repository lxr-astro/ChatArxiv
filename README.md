# ChatArxiv (Rewritten)

一个重写后的 arXiv 每日文献订阅项目，支持：
- `gpt-5-nano`（OpenAI Responses API）
- `gemini-3-pro-preview`（Google Generative Language API）

并修复了旧版本 arXiv 301 问题：
- 不再依赖旧 `arxiv` 包的老调用链
- 统一改用 `https://export.arxiv.org/api/query`（HTTPS）

## 1. 安装

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. 配置环境变量

```bash
# 任选一个 provider
export LLM_PROVIDER=openai
# export LLM_PROVIDER=gemini

# OpenAI
export OPENAI_API_KEY=your_openai_key
export OPENAI_MODEL=gpt-5-nano

# Gemini
export GEMINI_API_KEY=your_gemini_key
export GEMINI_MODEL=gemini-3-pro-preview

# GitHub issue
export GITHUB_TOKEN=your_github_token
export GITHUB_REPO_OWNER=your_name
export GITHUB_REPO_NAME=your_repo

# arXiv + keywords
export ARXIV_CATEGORY=astro-ph.GA
export KEYWORD_LIST="AGN,M87,blackhole"
```

## 3. 运行

### 只生成 Markdown

```bash
python main.py --mode generate
```

### 生成并创建 GitHub Issue

```bash
python main.py --mode all
```

### 使用 OpenAI（gpt-5-nano）

```bash
python main.py --provider openai --model gpt-5-nano --mode all
```

### 使用 Gemini（gemini-3-pro-preview）

```bash
python main.py --provider gemini --model gemini-3-pro-preview --mode all
```

## 4. 常用参数

```bash
python main.py \
  --provider openai \
  --keywords AGN M87 \
  --days-back 2 \
  --max-results 99 \
  --language zh \
  --mode all
```

## 5. GitHub Action

已提供 `.github/workflows/main.yml`，默认按 cron 定时运行，也支持手动触发。

## 6. 说明

- 默认统一入口 `main.py`，通过 `--provider` 切换模型供应商。
- 若输出内容过长，Issue 会自动分片创建。
- 若你更偏好“双文件版本”，可以在当前架构上再拆分为 `main_openai.py` 和 `main_gemini.py`，但核心逻辑已统一。 
