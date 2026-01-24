# 📘 EPUBTranslator — 智能文学级 EPUB 翻译工具

> 基于本地大模型 API（如 `llama.cpp` / `vLLM` / `Ollama`）的 EPUB 电子书翻译脚本，支持**断点续译**、**上下文感知**、**自定义 Prompt** 和 **双语对照输出**。

---

## ✨ 特性

- ✅ **保留原始 HTML 结构**：仅翻译 `<p>`、`<h1>`–`<h6>` 等文本节点，不破坏排版。
- 🔁 **断点续译 & 缓存机制**：自动缓存已翻译内容，中断后可继续，避免重复请求。
- 🧠 **上下文感知翻译**（可选）：对连续段落 `<p>` 启用前文记忆，提升连贯性。
- 🎯 **按标签类型定制 Prompt**：
  - 段落 (`<p>`)：使用“三步翻译法”文学级 prompt。
  - 标题 (`<h1>`–`<h6>`)：简洁准确，无标点。
  - 其他：通用翻译 prompt。
- 🛠️ **高度可配置**：
  - 自定义系统/用户 prompt（通过 JSON 配置文件）
  - 覆盖 API 请求 payload（如 `temperature`, `model` 等）
  - 支持添加 prompt 后缀（如 `/no_think`）
- 📊 **进度可视化**：使用 `tqdm` 显示翻译进度，可选静默模式。
- 📖 **双语对照输出**：
  - 原文加粗显示（`.original`）
  - 译文斜体+左侧边框（`.translation`）

---

## 📦 安装依赖

```bash
pip install -r requirements.txt
```

> ⚠️ 本工具**不包含模型**，需自行部署兼容 OpenAI Chat Completions API 的本地服务（如 [llama.cpp](https://github.com/ggerganov/llama.cpp) + `server`，或 [Ollama](https://ollama.com/)）。

默认连接地址：`http://localhost:1234/v1/chat/completions`

---

## ▶️ 快速使用

### 基础命令

```bash
python epub_translator.py book.epub -o book_zh.epub
```

### 启用上下文感知（推荐用于小说/散文）

```bash
python epub_translator.py book.epub --use-context
```

### 静默模式（仅显示进度条）

```bash
python epub_translator.py book.epub -q
```

### 自定义 API 地址

```bash
python epub_translator.py book.epub --api-url http://your-server:8000/v1/chat/completions
```

---

## ⚙️ 高级配置（JSON）

创建 `config.json`：

```json
{
  "prompt_config": {
    "p": {
      "system": "你是一位精通中英文学的翻译家。请将以下英文小说段落译为中文，保留原文的诗意与节奏，语言自然流畅。",
      "user_prefix": "翻译为中文：\n"
    },
    "heading": {
      "system": "将以下章节标题译为中文，简洁有力，不要加句号。",
      "user_prefix": "标题翻译：\n"
    }
  },
  "payload_overrides": {
    "temperature": 0.3,
    "top_p": 0.9,
    "model": "Qwen3-14B"
  },
  "prompt_suffix": "/no_think",
  "delay": 0.5,
  "save_interval": 20
}
```

使用配置文件：

```bash
python epub_translator.py book.epub --config config.json
```

> 所有命令行参数均可在配置文件中设置，命令行优先级更高。

---

## 📁 输出格式说明

生成的 EPUB 包含：

- 原文段落：`<p class="original">...</p>`
- 译文段落：`<p class="translation">...</p>`
- 内嵌 CSS 样式（位于 `style/trans.css`），实现双语对比排版。

---

## 🛑 注意事项

1. **模型要求**：API 必须返回标准 OpenAI 格式（含 `choices[0].message.content`）。
2. **缓存文件**：默认生成 `<输入文件>.json`，可手动删除以强制重译。
3. **中文编码**：确保终端支持 UTF-8，避免乱码。
4. **大文件处理**：建议配合 `--delay 0.5` 防止 API 过载。
5. **中断恢复**：程序被 `Ctrl+C` 中断时会自动保存缓存。

---
