import os
from pathlib import Path
from typing import Union, Dict, Any
import json


def create_code_file(filename: str, content: str, encoding: str = 'utf-8', overwrite: bool = False) -> Dict[str, Any]:
    """
    Создает файл с кодом из текстового содержимого

    Args:
        filename (str): Путь и имя создаваемого файла
        content (str): Содержимое файла
        encoding (str): Кодировка файла (по умолчанию utf-8)
        overwrite (bool): Перезаписывать существующий файл

    Returns:
        Dict: Результат операции
    """
    try:
        file_path = Path(filename)

        if file_path.exists() and not overwrite:
            return {
                'success': False,
                'error': f'Файл {filename} уже существует',
                'filename': str(file_path)
            }

        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Строгая запись - убираем лишние пробелы и пустые строки в конце
        cleaned_content = content.rstrip() + '\n'

        with open(file_path, 'w', encoding=encoding) as f:
            f.write(cleaned_content)

        validation_result = _validate_file_content(file_path, cleaned_content)

        return {
            'success': True,
            'filename': str(file_path),
            'extension': file_path.suffix.lower(),
            'size': file_path.stat().st_size,
            'encoding': encoding,
            'validation': validation_result
        }

    except Exception as e:
        return {
            'success': False,
            'error': f'Ошибка при создании файла: {str(e)}',
            'filename': filename
        }


def _validate_file_content(file_path: Path, content: str) -> Dict[str, Any]:
    file_ext = file_path.suffix.lower()
    validation = {'is_valid': True, 'warnings': []}

    if file_ext == '.json':
        try:
            json.loads(content)
        except json.JSONDecodeError as e:
            validation['is_valid'] = False
            validation['warnings'].append(f'Невалидный JSON: {e}')

    elif file_ext == '.py':
        try:
            compile(content, str(file_path), 'exec')
        except SyntaxError as e:
            validation['warnings'].append(f'Синтаксическая ошибка Python: {e}')

    return validation


def create_python_file(filename: str, code: str, overwrite: bool = False) -> Dict[str, Any]:
    if not filename.endswith('.py'):
        filename += '.py'

    # Очищаем Python код от лишних пробелов
    cleaned_code = _clean_python_code(code)
    return create_code_file(filename, cleaned_code, overwrite=overwrite)


def create_html_file(filename: str, html_content: str, overwrite: bool = False) -> Dict[str, Any]:
    if not filename.endswith(('.html', '.htm')):
        filename += '.html'
    return create_code_file(filename, html_content, overwrite=overwrite)


def create_json_file(filename: str, data: Union[dict, list, str], indent: int = 4, overwrite: bool = False) -> Dict[
    str, Any]:
    if not filename.endswith('.json'):
        filename += '.json'

    try:
        if isinstance(data, str):
            json.loads(data)
            content = data
        else:
            content = json.dumps(data, indent=indent, ensure_ascii=False)
    except (TypeError, json.JSONDecodeError) as e:
        return {
            'success': False,
            'error': f'Невалидные JSON данные: {e}',
            'filename': filename
        }

    return create_code_file(filename, content, overwrite=overwrite)


def create_javascript_file(filename: str, code: str, overwrite: bool = False) -> Dict[str, Any]:
    if not filename.endswith('.js'):
        filename += '.js'
    return create_code_file(filename, code, overwrite=overwrite)


def create_css_file(filename: str, css_content: str, overwrite: bool = False) -> Dict[str, Any]:
    if not filename.endswith('.css'):
        filename += '.css'
    return create_code_file(filename, css_content, overwrite=overwrite)


def create_text_file(filename: str, text: str, overwrite: bool = False) -> Dict[str, Any]:
    if not filename.endswith('.txt'):
        filename += '.txt'
    return create_code_file(filename, text, overwrite=overwrite)


def create_markdown_file(filename: str, markdown_content: str, overwrite: bool = False) -> Dict[str, Any]:
    if not filename.endswith('.md'):
        filename += '.md'
    return create_code_file(filename, markdown_content, overwrite=overwrite)


def _clean_python_code(code: str) -> str:
    """Очищает Python код от лишних пробелов и выравнивает отступы"""
    lines = code.split('\n')
    cleaned_lines = []

    for line in lines:
        stripped = line.rstrip()
        if stripped:  # Не добавляем полностью пустые строки
            cleaned_lines.append(stripped)
        elif cleaned_lines and cleaned_lines[-1]:  # Добавляем только одну пустую строку между блоками
            cleaned_lines.append('')

    # Убираем множественные пустые строки в конце
    while cleaned_lines and not cleaned_lines[-1]:
        cleaned_lines.pop()

    return '\n'.join(cleaned_lines) + '\n'


# Пример использования из других скриптов:
if __name__ == "__main__":
    # Пример создания Python файла со строгим форматированием
    python_code = """# solver.py
import re
import logging
from typing import Optional, Any

import ollama

logger = logging.getLogger("solver")
logger.addHandler(logging.NullHandler())

SYSTEM_COMMON_RU = (
    "Ты профессиональный ассистент. Отвечай подробно и точно. "
    "В веди диалог так, как попросит пользователь.\\n\\n"
    "ВАЖНО: ВЕРНИ ОТВЕТ В ВАЛИДНОМ MarkdownV2. "
    "Если есть код — используй fenced code blocks ```lang ... ```.\\n"
    "Все мат вычисления и решения задач представляй в виде кода на Python"
    "Не используй boxed вывод"
    "Если не уверен в факте — напиши 'Не уверен'.\\n"
)

SYSTEM_COMMON_EN = (
    "You are a professional assistant. Answer precisely and in detail as the user requests.\\n\\n"
    "IMPORTANT: RETURN THE ANSWER IN VALID MarkdownV2. "
    "Use fenced code blocks for code (```lang ... ```).\\n"
    "If unsure — write 'Not sure'.\\n"
)

def _detect_lang(text: str) -> str:
    return "ru" if re.search(r'[а-яА-Я]', text or "") else "en"

def build_model_prompt(text: str, model: str) -> dict:
    lang = _detect_lang(text)
    system = SYSTEM_COMMON_RU if lang == "ru" else SYSTEM_COMMON_EN
    return {"system": system, "user": text}

def _extract_text_from_ollama_resp(resp: Any) -> Optional[str]:
    if resp is None:
        return None
    if isinstance(resp, str):
        return resp
    if isinstance(resp, dict):
        for k in ("content", "text", "response", "result"):
            v = resp.get(k)
            if isinstance(v, str) and v.strip():
                return v
        choices = resp.get("choices")
        if isinstance(choices, (list, tuple)):
            parts = []
            for c in choices:
                if isinstance(c, dict):
                    msg = c.get("message")
                    if isinstance(msg, dict):
                        cont = msg.get("content") or msg.get("text")
                        if isinstance(cont, str):
                            parts.append(cont)
                    else:
                        for key in ("content", "text", "response"):
                            if isinstance(c.get(key), str):
                                parts.append(c.get(key))
                                break
                elif isinstance(c, str):
                    parts.append(c)
            if parts:
                return "\\n".join(parts)
    if isinstance(resp, (list, tuple)):
        parts = []
        for it in resp:
            if isinstance(it, str):
                parts.append(it)
            elif isinstance(it, dict):
                for k in ("content", "text", "response"):
                    if isinstance(it.get(k), str):
                        parts.append(it.get(k))
                        break
        if parts:
            return "\\n".join(parts)
    try:
        return str(resp)
    except Exception:
        return None

def query(text: str, model: str = "gpt-oss") -> Optional[str]:
    try:
        model_map = {
            "gpt-oss": "gpt-oss:120b-cloud",
            "gpt": "gpt-oss:120b-cloud",
            "deepseek": "deepseek-v3.1:671b-cloud",
        }
        key = (model or "").lower()
        model_name = model_map.get(key, model_map["gpt-oss"])

        prompt = build_model_prompt(text, model)
        messages = []
        if prompt.get("system"):
            messages.append({"role": "system", "content": prompt["system"]})
        messages.append({"role": "user", "content": prompt["user"]})

        resp = ollama.chat(model=model_name, messages=messages, stream=False)
        out = _extract_text_from_ollama_resp(resp)
        if out is None:
            logger.warning("solver.query: empty response (raw=%s)", repr(resp)[:300])
            return None
        return out
    except Exception:
        logger.exception("Ошибка в solver.query()")
        return None
"""

    result = create_python_file("solver", python_code)

    # Проверяем результат
    if result['success']:
        # Файл успешно создан
        pass
    else:
        # Обрабатываем ошибку
        error_msg = result['error']