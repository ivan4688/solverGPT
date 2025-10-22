import docx2txt
import re
import pandas as pd
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
import pdfplumber
import fitz
import pytesseract
from PIL import Image
import cv2
import numpy as np
import requests
import json
import base64
import logging

from src.utils.web import run_extraction

logger = logging.getLogger("ocr")


def doc2(filename: str) -> str:
    text = docx2txt.process(filename)
    cleaned_text = re.sub(r'\n{2,}', '\n\n', text.strip())
    return cleaned_text


def excel2text(filename: str, sheet_name=0):
    file_ext = os.path.splitext(filename)[1].lower()

    engine_map = {
        '.xlsx': 'openpyxl',
        '.xlsm': 'openpyxl',
        '.xls': 'xlrd',
        '.ods': 'odf'
    }
    engine = engine_map.get(file_ext)

    try:
        if engine:
            df = pd.read_excel(filename, sheet_name=sheet_name, engine=engine)
        else:
            df = pd.read_excel(filename, sheet_name=sheet_name)

        table_info = {
            'filename': filename,
            'sheet_name': sheet_name,
            'shape': df.shape,
            'columns': list(df.columns),
            'data_types': df.dtypes.to_dict()
        }

        return df, table_info

    except ImportError as e:
        error_info = {
            'error_type': 'ImportError',
            'message': str(e),
            'required_package': 'openpyxl' if file_ext in ['.xlsx', '.xlsm'] else
            'xlrd' if file_ext == '.xls' else
            'odfpy' if file_ext == '.ods' else 'unknown'
        }
        return None, error_info

    except Exception as e:
        error_info = {
            'error_type': type(e).__name__,
            'message': str(e)
        }
        return None, error_info


def get_excel_data_as_text(filename: str, sheet_name=0):
    df, info = excel2text(filename, sheet_name)

    if df is None:
        return f"Ошибка: {info['error_type']} - {info['message']}"

    result = []
    result.append(f"Файл: {info['filename']}")
    result.append(f"Лист: {info['sheet_name']}")
    result.append(f"Размер: {info['shape'][0]} строк, {info['shape'][1]} колонок")
    result.append(f"Колонки: {', '.join(info['columns'])}")
    result.append("\nДанные:")

    for idx, row in df.iterrows():
        row_data = {col: row[col] for col in df.columns if pd.notna(row[col])}
        if row_data:
            result.append(f"Строка {idx}: {row_data}")

    return '\n'.join(result)


def extract_code_file(filename: str) -> Dict[str, Any]:
    file_path = Path(filename)

    if not file_path.exists():
        return {
            'success': False,
            'error': f'Файл {filename} не существует',
            'content': None
        }

    try:
        content = _read_file_with_encoding(file_path)

        return {
            'success': True,
            'filename': str(file_path),
            'extension': file_path.suffix.lower(),
            'size': file_path.stat().st_size,
            'content': content,
            'line_count': len(content.splitlines()),
            'encoding': 'utf-8'
        }

    except UnicodeDecodeError:
        try:
            content = _read_file_with_fallback_encoding(file_path)
            return {
                'success': True,
                'filename': str(file_path),
                'extension': file_path.suffix.lower(),
                'size': file_path.stat().st_size,
                'content': content,
                'line_count': len(content.splitlines()),
                'encoding': 'detected'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Ошибка чтения файла: {str(e)}',
                'filename': str(file_path),
                'content': None
            }

    except Exception as e:
        return {
            'success': False,
            'error': f'Ошибка: {str(e)}',
            'filename': str(file_path),
            'content': None
        }


def _read_file_with_encoding(file_path: Path, encoding: str = 'utf-8') -> str:
    with open(file_path, 'r', encoding=encoding) as f:
        return f.read()


def _read_file_with_fallback_encoding(file_path: Path) -> str:
    encodings = ['utf-8', 'cp1251', 'iso-8859-1', 'koi8-r', 'utf-16']

    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue

    with open(file_path, 'rb') as f:
        binary_content = f.read()
        return binary_content.decode('utf-8', errors='replace')


def extract_code_simple(filename: str) -> Optional[str]:
    result = extract_code_file(filename)
    return result['content'] if result['success'] else None


def extract_python_code(filename: str) -> Optional[str]:
    content = extract_code_simple(filename)
    if content is None:
        return None

    try:
        compile(content, filename, 'exec')
        return content
    except SyntaxError as e:
        print(f"Внимание: синтаксическая ошибка в {filename}: {e}")
        return content


def extract_text_file(filename: str) -> Optional[str]:
    return extract_code_simple(filename)


def extract_json_file(filename: str) -> Optional[Any]:
    content = extract_code_simple(filename)
    if content is None:
        return None

    try:
        import json
        return json.loads(content)
    except json.JSONDecodeError as e:
        print(f"Ошибка парсинга JSON в {filename}: {e}")
        return content


def extract_text_from_pdf(pdf_path: str) -> Optional[str]:
    text = None

    try:
        with pdfplumber.open(pdf_path) as pdf:
            text_parts = []
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text and page_text.strip():
                    text_parts.append(page_text.strip())

            if text_parts:
                text = "\n".join(text_parts)
    except Exception:
        text = None

    if not text:
        try:
            with fitz.open(pdf_path) as doc:
                text_parts = []
                for page_num in range(len(doc)):
                    page = doc[page_num]
                    page_text = page.get_text()
                    if page_text and page_text.strip():
                        text_parts.append(page_text.strip())

                if text_parts:
                    text = "\n".join(text_parts)
        except Exception as e:
            print(f"Ошибка при извлечении текста из PDF: {e}")
            return None

    if text:
        cleaned_text = re.sub(r'\n{3,}', '\n\n', text.strip())
        cleaned_text = re.sub(r' +', ' ', cleaned_text)
        return cleaned_text

    return None


def pdf2text(filename: str) -> str:
    text = extract_text_from_pdf(filename)

    if text:
        return text
    else:
        return "Не удалось извлечь текст из PDF файла"


