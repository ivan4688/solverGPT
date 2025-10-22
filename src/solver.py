# solver.py
import re
import logging
import os
from typing import Optional, Any
import ollama
import src.utils.getdoc as u
from src.utils.test_OCR import analyze_test_image
from src.utils.web import run_extraction



logger = logging.getLogger("solver")
logger.addHandler(logging.NullHandler())

SYSTEM_COMMON_RU = (
    "Ты профессиональный ассистент. Отвечай подробно и точно. "
    "ВАЖНО: ВЕРНИ ОТВЕТ В ВАЛИДНОМ MarkdownV2. "
    "Если есть код — используй fenced code blocks ```lang ... ```.\n"
    "Абсолютно каждый расчет / формулу верни ввиде fenced code block"
    "Если не уверен в факте — напиши 'Не уверен'.\n"
    "Всегда будь доброжелательным и полезным"
)
SYS_INLINE = (
    "Ты профессиональный ассистент. Отвечай максимально коротко и точно. "
    "ВАЖНО: ВЕРНИ ОТВЕТ В ВАЛИДНОМ MarkdownV2. \n"
    "Если вопрос сложный и ты не можешь на него кратко ответить, так и напиши. \n"
    "Если не уверен в факте — напиши 'Не уверен'.\n"
)
SYS_WEB = (
    "Ты профессиональный ассистент. Отвечай максимально коротко и точно. "
    "ВАЖНО: ВЕРНИ ОТВЕТ В ВАЛИДНОМ MarkdownV2. \n"
    "Если вопрос сложный и ты не можешь на него кратко ответить, так и напиши. \n"
    "Если есть код — используй fenced code blocks ```lang ... ```.\n"
    "Абсолютно каждый расчет / формулу верни ввиде fenced code block"
    "Данные предоставленные тебе далее являются на 100% точными!"
    "Используй только те данные, что важны для запроса пользователя, лишнее - игнорируй!"
)


def _detect_lang(text: str) -> str:
    return "ru" if re.search(r'[а-яА-Я]', text or "") else "en"


def build_model_inline(text: str, model: str) -> dict:
    file_content = ""

    lang = _detect_lang(text)
    system = SYS_INLINE

    user_message = text

    logger.info(f"Final user message length: {len(user_message)}")
    return {"system": system, "user": user_message}


def _extract_text_from_ollama_resp(resp: Any) -> Optional[str]:
    if resp is None:
        return None

    if isinstance(resp, str):
        return resp

    if isinstance(resp, dict):
        # Основной формат ответа ollama
        if 'message' in resp and 'content' in resp['message']:
            return resp['message']['content']

        for k in ("content", "text", "response", "result"):
            v = resp.get(k)
            if isinstance(v, str) and v.strip():
                return v

    try:
        return str(resp)
    except Exception:
        return None

def build_model_prompt(text: str, model: str, file_path: Optional[str] = None) -> dict:
    file_content = ""

    if file_path and os.path.exists(file_path):
        try:
            file_ext = os.path.splitext(file_path)[1].lower()
            logger.info(f"Processing file: {file_path}, extension: {file_ext}")

            if file_ext == '.py':
                content = u.extract_python_code(file_path)
                file_content = f"Содержимое Python файла:\n```python\n{content}\n```" if content else "Не удалось извлечь Python код"
            elif file_ext == '.json':
                content = u.extract_json_file(file_path)
                if isinstance(content, str):
                    file_content = f"Содержимое JSON файла:\n```json\n{content}\n```"
                else:
                    file_content = f"Содержимое JSON файла (парсинг):\n{content}"
            elif file_ext == '.pdf':
                content = u.pdf2text(file_path)
                file_content = f"Содержимое PDF файла:\n{content}" if content and not content.startswith(
                    "Не удалось") else "Не удалось извлечь текст из PDF"
            elif file_ext == '.docx':
                content = u.doc2(file_path)
                file_content = f"Содержимое DOCX файла:\n{content}" if content else "Не удалось извлечь текст из DOCX"
            elif file_ext in ['.xlsm', '.xlsx', '.xls']:
                content = u.get_excel_data_as_text(file_path, 0)
                file_content = f"Содержимое Excel файла:\n{content}" if content else "Не удалось извлечь данные из Excel"
            elif file_ext in ['.png', '.jpg', '.jpeg', '.ttf']:
                content = analyze_test_image(file_path)
                file_content = f"Содержимое Изображения:\n{content}" if content else "Не удалось извлечь данные из Изображения"
            else:
                content = u.extract_text_file(file_path)
                file_content = f"Содержимое файла:\n{content}" if content else "Не удалось извлечь содержимое файла"

            logger.info(f"File content extracted successfully, length: {len(file_content)}")

        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
            file_content = f"Ошибка при обработке файла: {str(e)}"
    else:
        logger.warning(f"File not found: {file_path}")
        file_content = f"Файл не найден по пути: {file_path}"

    lang = _detect_lang(text)
    system = SYSTEM_COMMON_RU

    if file_path:
        if text and text.strip():
            # ЕСТЬ И ФАЙЛ И ТЕКСТ - явно указываем модели на оба
            user_message = (
                f"ПОЛЬЗОВАТЕЛЬ ОТПРАВИЛ ФАЙЛ И ТЕКСТОВЫЙ ЗАПРОС:\n\n"
                f"СОДЕРЖИМОЕ ФАЙЛА:\n{file_content}\n\n"
                f"ТЕКСТОВЫЙ ЗАПРОС ПОЛЬЗОВАТЕЛЯ: {text}\n\n"
                f"ПРОАНАЛИЗИРУЙ ФАЙЛ И ОТВЕТЬ НА ВОПРОС ПОЛЬЗОВАТЕЛЯ, ИСПОЛЬЗУЯ ИНФОРМАЦИЮ ИЗ ФАЙЛА."
            )
        else:
            # ТОЛЬКО ФАЙЛ БЕЗ ТЕКСТА
            user_message = (
                f"ПОЛЬЗОВАТЕЛЬ ОТПРАВИЛ ФАЙЛ:\n\n"
                f"СОДЕРЖИМОЕ ФАЙЛА:\n{file_content}\n\n"
                f"ПРОАНАЛИЗИРУЙ ЭТОТ ФАЙЛ И РАССКАЖИ, ЧТО В НЕМ СОДЕРЖИТСЯ."
            )
    else:
        # ТОЛЬКО ТЕКСТ БЕЗ ФАЙЛА
        user_message = text

    logger.info(f"Final user message length: {len(user_message)}")
    return {"system": system, "user": user_message}


def query(file_path: Optional[str], text: str, model: str = "deepseek") -> Optional[str]:
    try:
        model_map = {
            "gpt-oss": "gpt-oss:120b-cloud",
            "gpt": "gpt-oss:120b-cloud",
            "deepseek": "deepseek-v3.1:671b-cloud",
        }

        key = (model or "").lower()
        model_name = model_map.get(key, "deepseek-v3.1:671b-cloud")

        prompt = build_model_prompt(text, model, file_path)
        messages = []

        if prompt.get("system"):
            messages.append({"role": "system", "content": prompt["system"]})
        messages.append({"role": "user", "content": prompt["user"]})

        logger.info(f"Sending to model {model_name}, message length: {len(prompt['user'])}")

        resp = ollama.chat(model=model_name, messages=messages, stream=False)
        logger.info(f"Received response from model")

        out = _extract_text_from_ollama_resp(resp)

        if out is None:
            logger.warning("Empty response from model")
            return "Не удалось получить ответ от модели. Попробуйте еще раз."

        return out

    except Exception as e:
        logger.exception(f"Error in solver.query(): {e}")
        return f"Произошла ошибка: {str(e)}"

def query_inline(text: str, model: str = "deepseek") -> Optional[str]:
    try:
        model_map = {
            "gpt-oss": "gpt-oss:120b-cloud",
            "gpt": "gpt-oss:120b-cloud",
            "deepseek": "deepseek-v3.1:671b-cloud",
        }

        key = (model or "").lower()
        model_name = model_map.get(key, "deepseek-v3.1:671b-cloud")

        prompt = build_model_inline(text, model)
        messages = []

        if prompt.get("system"):
            messages.append({"role": "system", "content": prompt["system"]})
        messages.append({"role": "user", "content": prompt["user"]})

        logger.info(f"Sending to model {model_name}, message length: {len(prompt['user'])}")

        resp = ollama.chat(model=model_name, messages=messages, stream=False)
        logger.info(f"Received response from model")

        out = _extract_text_from_ollama_resp(resp)

        if out is None:
            logger.warning("Empty response from model")
            return "Не удалось получить ответ от модели. Попробуйте еще раз."

        return out

    except Exception as e:
        logger.exception(f"Error in solver.query(): {e}")
        return f"Произошла ошибка: {str(e)}"


def web_search(query: str):
    res = run_extraction(query, only_good_quality=True)
    return str(res["shortest_text"])

def prompt_web(text:str):
    web_res = str(web_search(text))
    lang = _detect_lang(text)
    system = SYS_WEB + f"\n{web_res}"

    user_message = text

    logger.info(f"Final user message length: {len(user_message)}")
    return {"system": system, "user": user_message}


def query_web(text, model: str = "deepseek") -> Optional[str]:
    """
    Если передан dict (готовый prompt от prompt_web), используем его напрямую.
    Иначе — формируем prompt через prompt_web(text).
    """
    try:
        model_map = {
            "gpt-oss": "gpt-oss:120b-cloud",
            "gpt": "gpt-oss:120b-cloud",
            "deepseek": "deepseek-v3.1:671b-cloud",
        }

        key = (model or "").lower()
        model_name = model_map.get(key, "deepseek-v3.1:671b-cloud")

        # Поддержка двух типов входа: str или уже подготовленный prompt (dict)
        if isinstance(text, dict):
            prompt = text
        else:
            prompt = prompt_web(text)

        messages = []
        if prompt.get("system"):
            messages.append({"role": "system", "content": prompt["system"]})
        messages.append({"role": "user", "content": prompt["user"]})

        logger.info(f"Sending to model {model_name}, message length: {len(prompt['user'])}")

        resp = ollama.chat(model=model_name, messages=messages, stream=False)
        logger.info(f"Received response from model")

        out = _extract_text_from_ollama_resp(resp)

        if out is None:
            logger.warning("Empty response from model")
            return "Не удалось получить ответ от модели. Попробуйте еще раз."

        return out

    except Exception as e:
        logger.exception(f"Error in solver.query_web(): {e}")
        return f"Произошла ошибка: {str(e)}"
