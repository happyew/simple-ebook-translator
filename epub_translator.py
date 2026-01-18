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

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EPUBTranslator:
    def __init__(self, api_url="http://localhost:5001/v1/chat/completions", target_language="zh"):
        """
        初始化EPUB翻译器
        
        :param api_url: 本地OpenAI API接口地址
        :param target_language: 目标翻译语言
        """
        self.api_url = api_url
        self.target_language = target_language
        self.session = requests.Session()
        
        # 设置请求头
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'EPUBTranslator/1.0'
        })

    def clean_think_tags(self, text):
        """
        清理<think>标签及其内容
        
        :param text: 原始文本
        :return: 清理后的文本
        """
        # 使用正则表达式移除<think>标签及其内容
        pattern = r'<think>.*?</think>'
        cleaned_text = re.sub(pattern, '', text, flags=re.DOTALL)
        return cleaned_text.strip()

    def translate_text(self, text):
        """
        调用本地API翻译文本
        
        :param text: 待翻译文本
        :return: 翻译后的文本
        """
        if not text.strip():
            return ""
            
        # 构建API请求数据
        payload = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {
                    "role": "system",
                    "content": f"你是一个专业的翻译助手，请将以下文本翻译成{self.target_language}。"
                },
                {
                    "role": "user",
                    "content": text
                }
            ],
            "temperature": 0.3,
            "max_tokens": 1000
        }

        try:
            response = self.session.post(self.api_url, json=payload, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            translated_text = result['choices'][0]['message']['content']
            
            # 清理<think>标签
            cleaned_text = self.clean_think_tags(translated_text)
            
            logger.info(f"成功翻译文本片段")
            return cleaned_text
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API请求失败: {e}")
            raise
        except KeyError as e:
            logger.error(f"解析API响应失败: {e}, 响应内容: {response.text}")
            raise
        except Exception as e:
            logger.error(f"翻译过程出错: {e}")
            raise

    def get_all_paragraphs(self, soup):
        """
        获取所有需要翻译的段落
        
        :param soup: BeautifulSoup对象
        :return: 段落列表
        """
        paragraphs = soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        # 过滤掉空段落
        valid_paragraphs = []
        for p in paragraphs:
            if p.get_text().strip():
                valid_paragraphs.append(p)
        return valid_paragraphs

    def process_paragraphs(self, soup, total_paragraphs):
        """
        处理HTML段落，逐段翻译并插入译文
        
        :param soup: BeautifulSoup对象
        :param total_paragraphs: 总段落数量
        :return: 更新后的BeautifulSoup对象
        """
        paragraphs = self.get_all_paragraphs(soup)
        
        logger.info(f"当前章节找到 {len(paragraphs)} 个段落需要翻译")
        
        # 使用tqdm显示进度条
        for i, p in enumerate(tqdm(paragraphs, desc="翻译进度", unit="段")):
            original_text = p.get_text().strip()
            
            # 如果段落为空或只有空白字符，则跳过
            if not original_text:
                continue
                
            current_index = getattr(self, 'current_index', 0)
            setattr(self, 'current_index', current_index + 1)
            current_pos = getattr(self, 'current_index')
            
            logger.info(f"正在翻译第({current_pos}/{total_paragraphs})段")
            
            try:
                # 翻译文本
                translated_text = self.translate_text(original_text)
                
                # 打印原文和译文
                print(f"\n--- 第({current_pos}/{total_paragraphs})段 ---")
                print(f"原文: {original_text}")
                print(f"译文: {translated_text}")
                print("-" * 70)
                
                # 创建新的段落元素用于存放翻译内容
                translation_p = soup.new_tag('p', **{'class': 'translation'})
                translation_p.string = translated_text
                
                # 在原文后插入译文
                p.insert_after(translation_p)
                
                # 添加一些样式以便区分原文和译文
                if p.get('class'):
                    p['class'] = p.get('class') + ['original']
                else:
                    p['class'] = ['original']
                    
                # 添加延时以避免API调用过于频繁
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"翻译第({current_pos}/{total_paragraphs})段时出错: {e}")
                print(f"错误: 翻译第({current_pos}/{total_paragraphs})段时出错 - {e}")
                continue
        
        return soup

    def count_total_paragraphs(self, book):
        """
        统计整个EPUB中所有需要翻译的段落数量
        
        :param book: EPUB书籍对象
        :return: 总段落数
        """
        total_count = 0
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                soup = BeautifulSoup(item.get_content(), 'html.parser')
                paragraphs = self.get_all_paragraphs(soup)
                total_count += len(paragraphs)
        return total_count

    def translate_epub(self, input_path, output_path):
        """
        主函数：翻译整个EPUB文件
        
        :param input_path: 输入EPUB文件路径
        :param output_path: 输出EPUB文件路径
        """
        logger.info(f"开始处理EPUB文件: {input_path}")
        
        # 读取EPUB文件
        book = epub.read_epub(input_path)
        
        # 统计总段落数
        total_paragraphs = self.count_total_paragraphs(book)
        logger.info(f"总共找到 {total_paragraphs} 个需要翻译的段落")
        
        # 重置全局索引
        self.current_index = 0
        
        # 遍历所有文档项
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                # 解析HTML内容
                soup = BeautifulSoup(item.get_content(), 'html.parser')
                
                # 处理段落并翻译
                updated_soup = self.process_paragraphs(soup, total_paragraphs)
                
                # 更新项目内容
                item.set_content(str(updated_soup).encode('utf-8'))
        
        # 设置CSS样式
        css_content = '''
        .original {
            font-weight: bold;
            margin-bottom: 0.5em;
        }
        .translation {
            color: #555;
            font-style: italic;
            margin-top: 0.2em;
            margin-bottom: 1em;
            padding-left: 1em;
            border-left: 2px solid #ccc;
        }
        '''
        
        # 创建CSS项目
        nav_css = epub.EpubItem(
            uid="style_nav",
            file_name="style/nav.css",
            media_type="text/css",
            content=css_content
        )
        
        # 添加CSS到书籍
        book.add_item(nav_css)
        
        # 写入新文件
        epub.write_epub(output_path, book, {})
        
        logger.info(f"翻译完成，输出文件: {output_path}")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='EPUB电子书翻译工具')
    parser.add_argument('input_file', help='输入EPUB文件路径')
    parser.add_argument('-o', '--output', help='输出EPUB文件路径', 
                       default='translated_book.epub')
    parser.add_argument('-l', '--language', help='目标翻译语言', 
                       default='zh')
    parser.add_argument('--api-url', help='本地API地址', 
                       default='http://localhost:5001/v1/chat/completions')
    
    args = parser.parse_args()
    
    # 验证输入文件是否存在
    if not os.path.exists(args.input_file):
        logger.error(f"输入文件不存在: {args.input_file}")
        return
    
    # 创建翻译器实例
    translator = EPUBTranslator(api_url=args.api_url, target_language=args.language)
    
    try:
        # 执行翻译
        translator.translate_epub(args.input_file, args.output)
        print(f"\n翻译完成！输出文件: {args.output}")
    except Exception as e:
        logger.error(f"翻译过程中发生错误: {e}")
        print(f"翻译失败: {e}")

if __name__ == "__main__":
    main()
