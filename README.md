# simple-ebook-translator

一个支持上下文感知的 EPUB 电子书翻译工具，能够调用本地 AI API 将英文 EPUB 电子书翻译成中文，并保留原文格式，为翻译后的内容添加美观的样式。

## 功能特点

- 🧠 **上下文感知翻译**：翻译时可携带前一段的原文和译文作为上下文，保证翻译风格和术语的一致性
- 📚 **完整保留EPUB格式**：不破坏原书的目录结构、章节划分和基本排版
- 🎨 **美观的样式设计**：原文加粗显示，译文斜体并添加左侧边框，区分清晰
- 📊 **进度可视化**：使用 tqdm 显示翻译进度，支持段落级别的进度跟踪
- 📝 **详细日志记录**：完整记录翻译过程，便于排查问题
- ⚡ **灵活配置**：支持自定义 API 地址、目标语言，可禁用上下文功能

## 环境要求

### 系统依赖
- Python 3.8+
- 网络连接（用于访问本地 AI API）

### Python 依赖
```bash
pip install requests ebooklib beautifulsoup4 tqdm
```

## 快速开始

### 1. 准备工作
确保你的本地 AI API 服务已启动（默认地址：`http://localhost:5001/v1/chat/completions`），并且支持 OpenAI 兼容的接口格式。

### 2. 基本使用
```bash
# 基础用法
python epub_translator.py your_book.epub

# 指定输出文件名
python epub_translator.py your_book.epub -o translated_book.epub

# 禁用上下文感知（每段独立翻译）
python epub_translator.py your_book.epub -C

# 指定自定义 API 地址
python epub_translator.py your_book.epub --api-url http://127.0.0.1:8000/v1/chat/completions
```

## 命令行参数说明

| 参数 | 简写 | 说明 | 默认值 |
|------|------|------|--------|
| `input_file` | - | 必需，输入的 EPUB 文件路径 | - |
| `--output` | `-o` | 输出的 EPUB 文件路径 | `translated_book.epub` |
| `--language` | `-l` | 目标翻译语言 | `zh` |
| `--api-url` | - | AI 翻译 API 的地址 | `http://localhost:5001/v1/chat/completions` |
| `--no-context` | `-C` | 禁用上下文感知翻译 | `False` |

## 核心功能详解

### 上下文感知翻译
默认情况下，工具会将前一段的原文和译文作为上下文发送给 AI，这样可以保证：
- 专业术语翻译的一致性
- 人物名称、地名翻译的统一性
- 整体翻译风格的连贯性

如果不需要此功能，可通过 `-C` 参数禁用。

### 翻译结果格式
- 原文：加粗显示，添加 `original` CSS 类
- 译文：灰色斜体，左侧带灰色边框，添加 `translation` CSS 类
- 每段译文紧跟在对应原文之后

### 错误处理
- 单个段落翻译失败时，会跳过该段落并记录日志，不影响整体翻译流程
- 空内容章节会被自动跳过
- 解析失败的章节会记录警告并跳过

## 自定义配置

### 修改翻译提示词
你可以修改 `translate_text` 方法中的 system prompt 来调整翻译风格：
```python
messages = [
    {
        "role": "system",
        "content": f"你是资深文学翻译专家，要求保留原文的文学美感和情感基调，使用优美流畅的中文表达，直接输出译文。",
    }
]
```

### 修改翻译模型
修改 `payload` 中的 `model` 参数：
```python
payload = {
    "model": "Qwen3-14B",  # 改为你的模型名称
    # ... 其他参数
}
```

### 修改样式
修改 `translate_epub` 方法中的 CSS 内容可以自定义原文和译文的显示样式：
```python
css = """
.original { font-weight: bold; margin-bottom: 0.5em; }
.translation {
    color: #555; font-style: italic; margin: 0.2em 0 1em 0;
    padding-left: 1em; border-left: 2px solid #ccc;
}
"""
```

## 常见问题

### Q: 翻译速度慢怎么办？
A: 可以减少 `time.sleep(1)` 的等待时间，或优化 AI 服务的响应速度。

### Q: 翻译后的 EPUB 文件无法打开？
A: 可能是 TOC 结构问题，工具已内置 TOC UID 修复功能，如仍有问题请检查原 EPUB 文件是否损坏。

### Q: API 调用失败？
A: 请检查：
1. API 地址是否正确
2. AI 服务是否正常运行
3. API 是否支持 OpenAI 兼容的接口格式
4. 网络是否通畅

## 总结

1. 该工具是一款基于本地 AI API 的 EPUB 翻译工具，核心优势是**上下文感知翻译**和**完整保留原书格式**
2. 使用前需确保本地 AI API 服务正常运行，安装好所需的 Python 依赖
3. 支持灵活的命令行参数配置，可根据需求启用/禁用上下文功能、自定义输出路径等
4. 翻译结果格式清晰，原文和译文区分明显，便于阅读