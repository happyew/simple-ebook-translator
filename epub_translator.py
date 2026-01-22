#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import requests
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import time
import logging
from tqdm import tqdm
import json
import hashlib
from pathlib import Path
import argparse
import atexit

# 新增依赖
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class EPUBTranslator:
    def __init__(
        self,
        api_url="http://localhost:1234/v1/chat/completions",
        use_context=True,
        cache_file=None,
        prompt_suffix="",
        delay=0.5,
        input_epub_path=None,
        quiet=False,
    ):
        self.api_url = api_url
        self.use_context = use_context
        self.prompt_suffix = prompt_suffix
        self.delay = delay
        self.quiet = quiet

        # 自动生成缓存文件名：输入.epub → 输入.json
        if cache_file is None:
            if input_epub_path:
                self.cache_file = Path(input_epub_path).with_suffix(".json")
            else:
                self.cache_file = Path("translation_cache.json")
        else:
            self.cache_file = Path(cache_file)

        self.session = requests.Session()
        self.session.headers.update(
            {"Content-Type": "application/json", "User-Agent": "EPUBTranslator/1.0"}
        )
        self.last_original = None
        self.last_translation = None

        self.translation_cache = self._load_cache()
        self._cache_modified = False

        # 注册退出时保存缓存
        atexit.register(self._save_cache)

    @staticmethod
    def get_local_name(tag):
        """从带命名空间的标签名中提取本地名，如 '{http://...}p' -> 'p'"""
        if not tag or not hasattr(tag, "name") or not tag.name:
            return None
        name = tag.name
        return name.split("}")[-1] if "}" in name else name

    def _load_cache(self):
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    cache = json.load(f)
                    logger.info(f"✅ 加载缓存: {len(cache)} 条记录")
                    return cache
            except Exception as e:
                logger.warning(f"⚠️ 缓存加载失败，使用空缓存: {e}")
        return {}

    def _save_cache(self):
        if not self._cache_modified:
            return
        try:
            temp_file = self.cache_file.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(self.translation_cache, f, ensure_ascii=False, indent=2)
            temp_file.replace(self.cache_file)
            self._cache_modified = False
            logger.debug("💾 缓存已保存")
        except Exception as e:
            logger.error(f"❌ 缓存保存失败: {e}")

    def _get_cache_key(self, text, tag_type="p"):
        # 将 tag_type 纳入缓存 key，允许同一文本在不同上下文（p/h）有不同译文
        key_str = f"{tag_type}:{text}"
        return hashlib.md5(key_str.encode("utf-8")).hexdigest()

    def clean_think_tags(self, text):
        pattern = r"\<think\>.*?\<\/think\>"
        return re.sub(pattern, "", text, flags=re.DOTALL).strip()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.RequestException, ValueError)),
        reraise=True,
    )
    def _call_translation_api(self, payload):
        response = self.session.post(self.api_url, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()

        if (
            "choices" not in data
            or not isinstance(data["choices"], list)
            or len(data["choices"]) == 0
        ):
            raise ValueError(f"API 返回无效 choices: {data}")
        choice = data["choices"][0]
        if "message" not in choice or "content" not in choice["message"]:
            raise ValueError(f"API 缺少 message.content: {choice}")

        return choice["message"]["content"]

    def _calculate_max_tokens(self, text: str) -> int:
        """根据原文长度动态计算 max_tokens"""
        char_count = len(text)

        # 系数可根据场景调整（此处用 2.0 保安全）
        estimated_tokens = int(char_count * 2.0)

        # 设置合理边界
        min_tokens = 100  # 避免极短文本分配过少
        max_tokens = 2000  # 不超过模型输出上限

        return min(max_tokens, max(min_tokens, estimated_tokens))

    def translate_text(self, text, tag_type="p", use_context_override=None):
        if not text.strip():
            return "", True

        cache_key = self._get_cache_key(text, tag_type)

        if cache_key in self.translation_cache:
            logger.debug(f"🔁 命中缓存 ({tag_type}): {text[:30]}...")
            return self.translation_cache[cache_key], True

        # 根据 tag_type 选择 system prompt
        if tag_type == "p":
            system_prompt = (
                "你是资深文学翻译专家，要求译文保留原文的文学美感和情感基调，"
                "不得保留任何外语单词，使用优美流畅的中文表达，直接输出译文。"
            )
        elif tag_type.startswith("h"):  # h1, h2, ..., h6
            system_prompt = (
                "你是资深文学翻译专家，请将以下标题翻译成简洁、准确、符合中文阅读习惯的文字，"
                "不要添加解释、引号、句号或其他标点，直接输出译文。"
            )
        else:
            system_prompt = (
                "你是资深文学翻译专家，请将以下外文翻译成中文，保持原意，语言自然。"
            )

        messages = [{"role": "system", "content": system_prompt}]

        should_use_context = (
            (
                use_context_override
                if use_context_override is not None
                else self.use_context
            )
            and self.last_original
            and self.last_translation
        )

        if should_use_context:
            messages.extend(
                [
                    {"role": "user", "content": self.last_original},
                    {"role": "assistant", "content": self.last_translation},
                ]
            )

        messages.append(
            {
                "role": "user",
                "content": f"原文：\n{text}{self.prompt_suffix}",
            }
        )

        payload = {
            "model": "Qwen3-14B",
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": self._calculate_max_tokens(text),
            "top_p": 0.8,
            "top_k": 20,
            "min_p": 0.0,
        }

        try:
            translated_text = self._call_translation_api(payload)
            cleaned_text = self.clean_think_tags(translated_text)

            self.translation_cache[cache_key] = cleaned_text
            self._cache_modified = True

            return cleaned_text, False

        except Exception as e:
            logger.error(f"翻译失败（已重试）: {e}")
            raise

    def get_all_paragraphs(self, soup):
        tags = ["p", "h1", "h2", "h3", "h4", "h5", "h6"]
        paragraphs = soup.find_all(tags)
        return [p for p in paragraphs if p.get_text().strip()]

    def process_paragraphs(self, soup, total_paragraphs, pbar=None):
        paragraphs = self.get_all_paragraphs(soup)
        logger.debug(f"当前章节找到 {len(paragraphs)} 个段落需要翻译")

        if not paragraphs:
            return soup

        for p in paragraphs:
            original_text = p.get_text().strip()
            if not original_text:
                continue

            self.current_index += 1

            tag_name = self.get_local_name(p).lower() if self.get_local_name(p) else ""
            is_paragraph = tag_name == "p"
            tag_type = tag_name  # e.g., "p", "h1", "h2", etc.

            try:
                use_ctx = is_paragraph  # 只有 <p> 使用上下文
                translated_text, from_cache = self.translate_text(
                    original_text, tag_type=tag_type, use_context_override=use_ctx
                )

                # 仅当未命中缓存且非静默模式时才打印原文与译文
                if not self.quiet and not from_cache:
                    print(
                        f"\n--- 第({self.current_index}/{total_paragraphs})段 [{tag_type}] ---"
                    )
                    print(f"\n原文:\n{original_text}")
                    print(f"\n译文:\n{translated_text}")
                    print("-" * 70)

                trans_tag = soup.new_tag("p", **{"class": "translation"})
                trans_tag.string = translated_text
                p.insert_after(trans_tag)

                classes = p.get("class", []) + ["original"]
                p["class"] = classes

                # ✅ 只有 <p> 才更新上下文历史
                if is_paragraph:
                    self.last_original = original_text
                    self.last_translation = translated_text

                if self.delay > 0:
                    time.sleep(self.delay)

                if pbar is not None:
                    pbar.update(1)

            except Exception as e:
                logger.error(f"跳过段落（错误: {e}）")
                if pbar is not None:
                    pbar.update(1)
                continue

        return soup

    def count_total_paragraphs(self, book):
        total = 0
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                content = item.get_content()
                if content:
                    soup = BeautifulSoup(content, "html.parser")
                    total += len(self.get_all_paragraphs(soup))
        return total

    def translate_epub(self, input_path, output_path):
        logger.info(f"开始处理EPUB: {input_path}")
        book = epub.read_epub(input_path)
        total_paragraphs = self.count_total_paragraphs(book)
        logger.info(f"共需翻译 {total_paragraphs} 段")
        self.current_index = 0

        start_time = time.time()

        try:
            with tqdm(total=total_paragraphs, desc="翻译进度", unit="段") as pbar:
                for item in book.get_items():
                    if item.get_type() != ebooklib.ITEM_DOCUMENT:
                        continue

                    self.last_original = None
                    self.last_translation = None

                    content = item.get_content()
                    if not content:
                        logger.debug(f"跳过空内容项: {item.file_name}")
                        continue

                    try:
                        soup = BeautifulSoup(content, "html.parser")
                    except Exception as e:
                        logger.warning(f"解析失败，跳过 {item.file_name}: {e}")
                        continue

                    updated_soup = self.process_paragraphs(
                        soup, total_paragraphs, pbar=pbar
                    )
                    if updated_soup is None:
                        logger.error(
                            f"意外：process_paragraphs 返回 None ({item.file_name})"
                        )
                        continue

                    try:
                        new_content = str(updated_soup).encode("utf-8")
                        item.set_content(new_content)
                    except Exception as e:
                        logger.error(f"写入内容失败 ({item.file_name}): {e}")
                        continue

            css = """
            .original { font-weight: bold; margin-bottom: 0.5em; }
            .translation {
                color: #555; font-style: italic; margin: 0.2em 0 1em 0;
                padding-left: 1em; border-left: 2px solid #ccc;
            }
            """
            css_item = epub.EpubItem(
                uid="style_trans",
                file_name="style/trans.css",
                media_type="text/css",
                content=css,
            )
            book.add_item(css_item)

            def fix_toc_uids(toc, counter=None):
                if counter is None:
                    counter = [0]
                for item in toc:
                    if hasattr(item, "uid"):
                        if item.uid is None:
                            counter[0] += 1
                            item.uid = f"toc_fixed_{counter[0]}"
                    elif isinstance(item, (list, tuple)) and len(item) >= 1:
                        children = item[1] if len(item) > 1 else []
                        if isinstance(children, list):
                            fix_toc_uids(children, counter)

            fix_toc_uids(book.toc)

            epub.write_epub(output_path, book, {})

            end_time = time.time()
            total_seconds = end_time - start_time
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            logger.info(f"✅ 翻译完成: {output_path}")
            logger.info(
                f"⏱️ 总耗时: {int(hours)}小时 {int(minutes)}分 {seconds:.2f}秒 "
                f"(共 {total_paragraphs} 段，平均 {total_seconds / total_paragraphs:.2f} 秒/段)"
            )

        finally:
            self._save_cache()


def main():
    parser = argparse.ArgumentParser(
        description="支持断点续译、保留HTML标签、自定义prompt后缀的EPUB翻译工具"
    )
    parser.add_argument("input_file", help="输入EPUB路径")
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="输出路径（默认: <输入文件>_translated.epub）",
    )
    parser.add_argument(
        "--api-url", default="http://localhost:1234/v1/chat/completions", help="API地址"
    )
    parser.add_argument(
        "--no-context",
        "-C",
        action="store_true",
        help="禁用上下文感知翻译",
    )
    parser.add_argument(
        "--cache",
        default=None,
        help="翻译缓存文件路径（默认: <输入文件>.json）",
    )
    parser.add_argument(
        "--prompt-suffix",
        default="",
        help="附加到用户 prompt 末尾的字符串（例如 '/no_think'）",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0,
        help="每段翻译后的延迟（秒），避免 API 过载（默认: 0）",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="静默模式：不显示原文与译文，仅显示进度",
    )

    args = parser.parse_args()

    if not os.path.exists(args.input_file):
        logger.error(f"❌ 输入文件不存在: {args.input_file}")
        return

    if args.output is None:
        input_path = Path(args.input_file)
        args.output = str(input_path.with_stem(input_path.stem + "_translated"))

    translator = EPUBTranslator(
        api_url=args.api_url,
        use_context=not args.no_context,
        cache_file=args.cache,
        prompt_suffix=args.prompt_suffix,
        delay=args.delay,
        input_epub_path=args.input_file,
        quiet=args.quiet,
    )
    try:
        translator.translate_epub(args.input_file, args.output)
        print(f"\n🎉 翻译成功！输出文件: {os.path.abspath(args.output)}")
    except KeyboardInterrupt:
        logger.info("🛑 用户中断翻译，正在保存缓存...")
        translator._save_cache()
        print("\n⚠️  已保存缓存，下次可继续翻译。")
        return
    except Exception as e:
        logger.exception("💥 翻译过程崩溃")
        print(f"\n❌ 翻译失败: {e}")
        # 可选：崩溃时也保存缓存
        translator._save_cache()


if __name__ == "__main__":
    main()
