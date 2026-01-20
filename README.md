# 📘 EPUBTranslator —— 支持断点续译与 `/no_think` 指令的智能 EPUB 翻译工具

> 一款基于大语言模型（LLM）的 EPUB 电子书翻译脚本，支持上下文感知、缓存加速、断点续译，并可启用 `/no_think` 模式以提升翻译效率。

---

## ✨ 特性

- **双语对照输出**：原文保留并加粗，译文以斜体+左侧边框呈现，清晰易读。
- **智能缓存机制**：自动缓存已翻译段落，避免重复请求，支持断点续译。
- **上下文感知翻译**（可选）：利用前一段原文与译文作为上下文，提升连贯性。
- **`/no_think` 模式支持**：适用于兼容该指令的本地模型（如部分 Ollama/Qwen 部署），跳过推理过程直接输出。
- **进度可视化**：使用 `tqdm` 显示全局翻译进度。
- **结构保持完整**：保留原始 EPUB 的章节结构、TOC 目录等元信息。
- **错误容错**：单段翻译失败不会中断整个流程。

---

## 🛠️ 依赖环境

- Python 3.8+
- 必需库：
  ```bash
  pip install requests ebooklib beautifulsoup4 tqdm
  ```

> 注意：`ebooklib` 在某些系统上可能需要额外安装 `lxml`：
> ```bash
  pip install lxml
  ```

---

## ⚙️ 使用方法

### 基本用法

```bash
python epub_translator.py input_book.epub -o output_book.epub
```

### 完整参数说明

```bash
usage: epub_translator.py [-h] [-o OUTPUT] [-l LANGUAGE] [--api-url API_URL]
                          [--no-context] [--cache CACHE] [--no-think]
                          input_file

支持断点续译与/no_think开关的EPUB翻译工具

positional arguments:
  input_file            输入EPUB路径

optional arguments:
  -h, --help            显示帮助信息并退出
  -o OUTPUT, --output OUTPUT
                        输出路径（默认: translated_book.epub）
  -l LANGUAGE, --language LANGUAGE
                        目标语言（默认: zh）
  --api-url API_URL     LLM API 地址（默认: http://localhost:1234/v1/chat/completions）
  --no-context, -C      禁用上下文感知翻译
  --cache CACHE         翻译缓存文件路径（默认: translation_cache.json）
  --no-think            启用 /no_think 后缀（仅适用于支持该指令的模型）
```

### 示例

#### 1. 使用默认设置翻译（带上下文 + 缓存）

```bash
python epub_translator.py my_book.epub -o my_book_zh.epub
```

#### 2. 启用 `/no_think` 模式（适用于本地 Qwen/Ollama 等）

```bash
python epub_translator.py book.epub --no-think --api-url http://localhost:5001/v1/chat/completions
```

#### 3. 禁用上下文（更快但可能牺牲连贯性）

```bash
python epub_translator.py book.epub -C
```

#### 4. 自定义缓存文件

```bash
python epub_translator.py book.epub --cache my_cache.json
```

---

## 🌐 兼容的 LLM 服务

本工具通过标准 OpenAI-style Chat Completions API 调用模型，兼容以下部署方式：

- [Ollama](https://ollama.com/)（配合 `openai-compatible` API）
- [LM Studio](https://lmstudio.ai/)
- [OpenRouter](https://openrouter.ai/)
- 本地部署的 **Qwen3**, **Llama 3**, **DeepSeek** 等（需提供 `/v1/chat/completions` 接口）

> 默认模型为 `Qwen3-14B`，可在代码中修改 `payload["model"]` 以适配其他模型。

---

## 💾 缓存机制

- 所有翻译结果会按 **MD5(原文)** 存入 JSON 缓存文件。
- 下次运行相同或部分重叠内容时，自动跳过已翻译段落。
- 缓存每处理 10 段自动保存一次，程序退出时强制保存。

---

## 📂 输出样式预览

生成的 EPUB 中，每段将呈现为：

```html
<p class="original">Original English paragraph...</p>
<p class="translation">优美流畅的中文译文……</p>
```

配套 CSS 样式确保阅读体验清晰美观。

---

## ⚠️ 注意事项

1. **API 地址必须正确**：确保本地或远程 LLM 服务正在运行且路径匹配。
2. **模型需支持长文本**：建议使用支持 4K+ 上下文的模型。
3. **`/no_think` 并非通用**：仅在特定模型（如部分 Qwen 部署）中有效，普通 OpenAI API 会忽略该后缀。
4. **首次运行较慢**：无缓存时需逐段请求，建议在稳定网络环境下运行。
5. **EPUB 结构复杂时可能解析异常**：如遇问题可尝试简化源文件或提交 issue。

---

## 📜 许可证

MIT License — 自由使用、修改、分发。

---

## 🙌 致谢

- [ebooklib](https://github.com/aerkalov/ebooklib)
- [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/)
- [tqdm](https://github.com/tqdm/tqdm)

---

> 📩 如有建议或问题，欢迎提交 Issue 或 PR！  
> ✉️ 作者：AI 助手（基于 Qwen3） | 更新日期：2026年1月