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

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class EPUBTranslator:
    def __init__(
        self,
        api_url="http://localhost:5001/v1/chat/completions",
        target_language="zh",
        use_context=True,
        cache_file="translation_cache.json",
        use_no_think=False,  # ← 新增参数
    ):
        self.api_url = api_url
        self.target_language = target_language
        self.use_context = use_context
        self.use_no_think = use_no_think  # ← 控制 /no_think
        self.cache_file = Path(cache_file)
        self.session = requests.Session()
        self.session.headers.update(
            {"Content-Type": "application/json", "User-Agent": "EPUBTranslator/1.0"}
        )
        self.last_original = None
        self.last_translation = None

        self.translation_cache = self._load_cache()
        self._cache_modified = False

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

    def _get_cache_key(self, text):
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    def clean_think_tags(self, text):
        pattern = r"<think>.*?</think>"
        return re.sub(pattern, "", text, flags=re.DOTALL).strip()

    def translate_text(self, text):
        if not text.strip():
            return ""

        cache_key = self._get_cache_key(text)

        if cache_key in self.translation_cache:
            logger.debug(f"🔁 命中缓存: {text[:30]}...")
            cached_translation = self.translation_cache[cache_key]
            self.last_original = text
            self.last_translation = cached_translation
            return cached_translation

        messages = [
            {
                "role": "system",
                "content": "你是资深文学翻译专家，要求保留原文的文学美感和情感基调，使用优美流畅的中文表达，直接输出译文。",
            }
        ]

        if self.use_context and self.last_original and self.last_translation:
            messages.extend(
                [
                    {"role": "user", "content": self.last_original},
                    {"role": "assistant", "content": self.last_translation},
                ]
            )

        # 👇 关键修改：动态添加 /no_think
        prompt_suffix = "/no_think" if self.use_no_think else ""
        messages.append(
            {
                "role": "user",
                "content": f"请将以下英文段落完整翻译为中文，**不得保留任何英文单词**，所有内容必须译为地道中文：\n{text}{prompt_suffix}",
            }
        )

        payload = {
            "model": "Qwen3-14B",
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1000,
            "top_p": 0.8,
            "top_k": 20,
            "min_p": 0.0,
        }

        try:
            response = self.session.post(self.api_url, json=payload, timeout=60)
            response.raise_for_status()
            translated_text = response.json()["choices"][0]["message"]["content"]
            cleaned_text = self.clean_think_tags(translated_text)

            self.translation_cache[cache_key] = cleaned_text
            self._cache_modified = True
            if len(self.translation_cache) % 10 == 0:
                self._save_cache()

            self.last_original = text
            self.last_translation = cleaned_text
            return cleaned_text

        except Exception as e:
            logger.error(f"翻译失败: {e}")
            raise

    def get_all_paragraphs(self, soup):
        tags = ["p", "h1", "h2", "h3", "h4", "h5", "h6"]
        paragraphs = soup.find_all(tags)
        return [p for p in paragraphs if p.get_text().strip()]

    def process_paragraphs(self, soup, total_paragraphs, pbar=None):
        paragraphs = self.get_all_paragraphs(soup)
        logger.info(f"当前章节找到 {len(paragraphs)} 个段落需要翻译")

        if not paragraphs:
            return soup

        for p in paragraphs:
            original_text = p.get_text().strip()
            if not original_text:
                continue

            self.current_index += 1

            try:
                translated_text = self.translate_text(original_text)

                print(f"\n--- 第({self.current_index}/{total_paragraphs})段 ---")
                print(f"原文: {original_text}")
                print(f"译文: {translated_text}")
                print("-" * 70)

                trans_tag = soup.new_tag("p", **{"class": "translation"})
                trans_tag.string = translated_text
                p.insert_after(trans_tag)

                classes = p.get("class", []) + ["original"]
                p["class"] = classes

                time.sleep(0.5)

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
            with tqdm(total=total_paragraphs, desc="全局翻译进度", unit="段") as pbar:
                for item in book.get_items():
                    if item.get_type() != ebooklib.ITEM_DOCUMENT:
                        continue

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
        description="支持断点续译与/no_think开关的EPUB翻译工具"
    )
    parser.add_argument("input_file", help="输入EPUB路径")
    parser.add_argument(
        "-o", "--output", default="translated_book.epub", help="输出路径"
    )
    parser.add_argument("-l", "--language", default="zh", help="目标语言")
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
        default="translation_cache.json",
        help="翻译缓存文件路径",
    )
    parser.add_argument(
        "--no-think",
        action="store_true",
        help="增加/no_think 后缀（只适用于支持该指令的模型）",
    )  # ← 新增开关
    args = parser.parse_args()

    if not os.path.exists(args.input_file):
        logger.error(f"❌ 输入文件不存在: {args.input_file}")
        return

    translator = EPUBTranslator(
        api_url=args.api_url,
        target_language=args.language,
        use_context=not args.no_context,
        cache_file=args.cache,
        use_no_think=args.no_think,  # ← 默认不启用，除非用户指定 --no-think
    )
    try:
        translator.translate_epub(args.input_file, args.output)
        print(f"\n🎉 翻译成功！输出文件: {os.path.abspath(args.output)}")
    except Exception as e:
        logger.exception("💥 翻译过程崩溃")
        print(f"\n❌ 翻译失败: {e}")


if __name__ == "__main__":
    main()
