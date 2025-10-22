# saver.py
import re
import codecs
import html
import logging
from typing import Optional, Tuple, List

import telebot

logger = logging.getLogger("saver")
logger.addHandler(logging.NullHandler())

# --- Constants
DEFAULT_MAX_LEN = 4000  # safety margin (< Telegram 4096)


# ----- Content extraction & decoding -----
def extract_content(text: Optional[str]) -> str:
    """
    Извлекает возможное content="..." и нормализует вход:
    - декодирует escape-последовательности
    - unescape HTML entities
    - попытка исправить mojibake
    - убирает лишние двойные слэши
    - обрабатывает math expressions
    - нормализует для MarkdownV2 (с сохранением fenced code)
    Возвращает MarkdownV2-safe строку (но не обрезает по длине).
    """
    if not text:
        return ""

    if not isinstance(text, str):
        try:
            text = str(text)
        except Exception:
            return ""

    # Если есть content="..." либо content='...' — выбираем содержимое
    m = re.search(r'content=(["\'])(.*?)(?<!\\)\1', text, re.DOTALL)
    raw = m.group(2) if m else text

    # Декодируем стандартные escape-последовательности (\n \t \uXXXX)
    try:
        decoded = codecs.decode(raw, 'unicode_escape')
    except Exception:
        decoded = raw

    # Очистка контрол-символов, явных двойных слэшей
    decoded = decoded.replace('\\r\\n', '\n').replace('\\n', '\n').replace('\\t', '\t')
    decoded = decoded.replace('\\\\', '\\')

    # HTML entities
    decoded = html.unescape(decoded)

    # Попытка исправить mojibake (latin-1 -> utf-8) если похоже на кириллицу
    try:
        candidate = decoded.encode('latin-1').decode('utf-8')
        if re.search(r'[\u0400-\u04FF]', candidate):
            decoded = candidate
    except Exception:
        pass

    # Удаляем управляющие символы кроме \n и \t
    decoded = ''.join(ch for ch in decoded if ch == '\n' or ch == '\t' or (ord(ch) >= 32))

    # Обрабатываем математические конструкции (по имеющемуся коду)
    try:
        decoded = process_math_expressions(decoded)
    except Exception:
        # если что-то пошло не так — оставляем как есть
        logger.debug("process_math_expressions failed", exc_info=True)

    # Нормализуем текст под MarkdownV2, сохраняя fenced code blocks
    try:
        normalized = normalize_for_markdownv2(decoded)
    except Exception:
        # На крайний случай сделаем минимальную экранизацию
        normalized = html.unescape(decoded)
        normalized = re.sub(r'([\\\[\]\(\)~>#+=\-|{}\.\!])', r'\\\1', normalized)

    return normalized.strip()


# ----- Math expressions processing -----
def process_math_expressions(text: str) -> str:
    """
    Упрощает/заменяет LaTeX-like конструкции на читаемые символы/формат.
    Также автоматически собирает формулы/реакции в fenced code blocks.
    """
    if not text:
        return text

    # \frac{a}{b} -> either unicode fraction or a/b
    def replace_frac(match):
        numerator = match.group(1).strip()
        denominator = match.group(2).strip()
        simple_fracs = {
            ('1', '2'): '½', ('1', '3'): '⅓', ('2', '3'): '⅔',
            ('1', '4'): '¼', ('3', '4'): '¾', ('1', '5'): '⅕',
            ('2', '5'): '⅖', ('3', '5'): '⅗', ('4', '5'): '⅘',
            ('1', '6'): '⅙', ('5', '6'): '⅚', ('1', '8'): '⅛',
            ('3', '8'): '⅜', ('5', '8'): '⅝', ('7', '8'): '⅞',
        }
        if (numerator, denominator) in simple_fracs:
            return simple_fracs[(numerator, denominator)]
        return f"{numerator}/{denominator}"

    patterns = [
        (r'\\frac\{([^}]+)\}\{([^}]+)\}', replace_frac),
        (r'\\sqrt\{([^}]+)\}', r'√\1'),
        (r'\\sqrt\[([^]]+)\]\{([^}]+)\}', r'\1√\2'),
        (r'\^\{([^}]+)\}', r'^\1'),
        (r'\_\{([^}]+)\}', r'_\1'),
        (r'\\cdot', '·'),
        (r'\\times', '×'),
        (r'\\pm', '±'),
        (r'\\mp', '∓'),
        (r'\\leq', '≤'),
        (r'\\geq', '≥'),
        (r'\\neq', '≠'),
        (r'\\approx', '≈'),
        (r'\\infty', '∞'),
        (r'\\pi', 'π'),
        (r'\\alpha', 'α'),
        (r'\\beta', 'β'),
        (r'\\gamma', 'γ'),
        (r'\\delta', 'δ'),
        (r'\\epsilon', 'ε'),
        (r'\\theta', 'θ'),
        (r'\\lambda', 'λ'),
        (r'\\mu', 'μ'),
        (r'\\sigma', 'σ'),
        (r'\\omega', 'ω'),
        # arrows and reaction signs
        (r'\\rightarrow', '→'),
        (r'\\to', '→'),
        (r'\\leftrightarrow', '↔'),
        (r'\\leftrightarrows', '↔'),
        (r'\\rightleftharpoons', '⇌'),
        (r'\\updownarrow', '↕'),
        (r'\\uparrow', '↑'),
        (r'\\downarrow', '↓'),
        (r'->', '→'),
        (r'=>', '⇒'),
        (r'←', '←'),
        (r'\{([a-zA-Z0-9+\-*/^()]+)\}', r'\1'),
        (r'(\d+)\.0*\\circ', r'\1°'),
        (r'\\circ', '°'),
    ]

    res = text
    for pat, repl in patterns:
        try:
            if callable(repl):
                res = re.sub(pat, repl, res)
            else:
                res = re.sub(pat, repl, res)
        except Exception:
            logger.debug("pattern replace failed for %s", pat, exc_info=True)

    # Дополнительная оптимизация дробных выражений
    res = optimize_math_expression(res)

    # Автоматически оборачиваем вероятные формулы/реакции в fenced code blocks
    res = wrap_formulas_in_codeblocks(res)

    return res


def optimize_math_expression(text: str) -> str:
    """
    Простейшие упрощения дробных выражений.
    """
    if not text:
        return text

    def simplify_fraction_expression(match):
        try:
            whole = match.group(1)
            num = int(match.group(2))
            den = int(match.group(3))
            if num < den:
                return match.group(0)
            else:
                return f"{whole} - {num - den}/{den}"
        except Exception:
            return match.group(0)

    text = re.sub(r'(\d+)\s*-\s*(\d+)/(\d+)', simplify_fraction_expression, text)
    text = re.sub(r'\(\s*(\d+/\d+)\s*\)', r'\1', text)
    return text


# ----- Helpers for fenced code blocks preservation -----
_FENCED_RE = re.compile(r'```(?:([\w\-\+]+)\n)?(.*?)(?:\n)?```', flags=re.DOTALL)


def split_fenced(text: str):
    """
    Возвращает список сегментов: ("text", str) или ("code", (lang, content))
    Сохраняет порядок оригинала.
    """
    segments = []
    pos = 0
    for m in _FENCED_RE.finditer(text):
        s, e = m.span()
        if s > pos:
            segments.append(("text", text[pos:s]))
        lang = m.group(1) or ""
        content = m.group(2) or ""
        segments.append(("code", (lang, content)))
        pos = e
    if pos < len(text):
        segments.append(("text", text[pos:]))
    return segments


# ----- Normalization & escaping rules -----
# Removed [] and backslash from this reserved set to reduce annoying visible escapes;
# parentheses and other MarkdownV2-sensitive chars are still escaped.
_RESERVED_TO_ESCAPE_RE = re.compile(r'([()\~>#+=\-|{}\.\!])')  # removed brackets and backslash and slash


def normalize_for_markdownv2(text: str) -> str:
    """
    Сохраняет fenced code blocks, в текстовых сегментах делает:
    - убирает лишние backslashes перед обычными символами
    - преобразует **bold** -> *bold* и __italic__ -> _italic_
    - превращает заголовки "#..." в *...'*
    - экранирует оставшиеся зарезервированные символы (MarkdownV2)
    """
    if not text:
        return ""

    segments = split_fenced(text)
    out_parts = []

    for kind, content in segments:
        if kind == "code":
            lang, code = content
            if lang:
                out_parts.append(f"```{lang}\n{code}\n```")
            else:
                out_parts.append(f"```\n{code}\n```")
            continue

        seg = content
        # remove escapes like "\." -> "."
        seg = re.sub(r'\\([_\*\`\[\]\(\)\.\,\!\-\+])', r'\1', seg)

        # **bold** -> *bold*, __ital__ -> _ital_
        seg = re.sub(r'\*\*(.+?)\*\*', r'*\1*', seg, flags=re.DOTALL)
        seg = re.sub(r'__(.+?)__', r'_\1_', seg, flags=re.DOTALL)

        # headers -> bold
        seg = re.sub(r'(^|\n)(\s{0,3}#{1,6})\s+(.+?)(?=\n|$)',
                     lambda m: f"{m.group(1)}*{m.group(3).strip()}*\n", seg, flags=re.MULTILINE)

        # unescape \( \) and \[ \]
        seg = seg.replace(r'\(', '(').replace(r'\)', ')').replace(r'\[', '[').replace(r'\]', ']')

        # Remove stray backslashes that are not part of intended escapes
        seg = seg.replace('\\', '')

        # Remove stray square brackets and forward slashes in non-code text that often come from OCR / model noise
        # (Important: real formulas should already be wrapped in code blocks and won't be affected)
        seg = seg.replace('[', '').replace(']', '')
        seg = seg.replace('/', ' / ')  # keep visible division but spaced

        # escape reserved chars for MarkdownV2 (except '*', '_', '`')
        seg = _RESERVED_TO_ESCAPE_RE.sub(r'\\\1', seg)

        out_parts.append(seg)

    return "".join(out_parts)


# ----- Assemble messages preserving multiple code blocks in one message -----
def assemble_send_parts_from_segments(segments: List[Tuple[str, object]], max_len: int = DEFAULT_MAX_LEN) -> List[str]:
    """
    Из списка сегментов (как возвращает split_fenced) собирает список сообщений,
    пытаясь уместить как можно больше сегментов в одно сообщение при условии max_len.
    Если отдельный code-block длиннее max_len, он будет порезан на части внутри ``` ```
    """
    if not segments:
        return []

    parts: List[str] = []
    cur = ""
    for kind, data in segments:
        if kind == "text":
            chunk = data
        else:
            lang, code = data
            code_block = f"```{lang}\n{code}\n```" if lang else f"```\n{code}\n```"
            chunk = code_block

        # If chunk is short enough to append to current message
        if len(cur) + len(chunk) <= max_len:
            cur += chunk
            continue

        # If chunk itself fits into an empty message -> finalize current and start new
        if len(chunk) <= max_len:
            if cur:
                parts.append(cur)
            cur = chunk
            continue

        # chunk too big (usually a huge code block). Need to split code content
        if kind == "code":
            lang, code = data
            # compute overhead of code fence
            fence_prefix = f"```{lang}\n" if lang else "```\n"
            fence_suffix = "\n```"
            overhead = len(fence_prefix) + len(fence_suffix)
            available = max_len - overhead
            if available <= 100:
                # fallback: just cut raw chunk into slices (rare)
                if cur:
                    parts.append(cur)
                i = 0
                raw = chunk
                while i < len(raw):
                    parts.append(raw[i:i + max_len])
                    i += max_len
                cur = ""
            else:
                # slice code content
                i = 0
                while i < len(code):
                    piece = code[i:i + available]
                    block = fence_prefix + piece + fence_suffix
                    if cur:
                        parts.append(cur)
                        cur = ""
                    parts.append(block)
                    i += available
        else:
            # plain text chunk longer than max_len
            # we try to split by lines
            if cur:
                parts.append(cur)
                cur = ""
            txt = data
            lines = txt.splitlines(keepends=True)
            buf = ""
            for ln in lines:
                if len(buf) + len(ln) > max_len:
                    if buf:
                        parts.append(buf)
                    # if single line > max_len, hard-cut
                    if len(ln) > max_len:
                        j = 0
                        while j < len(ln):
                            parts.append(ln[j:j + max_len])
                            j += max_len
                        buf = ""
                    else:
                        buf = ln
                else:
                    buf += ln
            if buf:
                parts.append(buf)

    if cur:
        parts.append(cur)
    # strip empty parts and trim trailing spaces
    return [p.rstrip() for p in parts if p and p.strip()]


# ----- Public API: replaced send_with_auto_parse (prepares parts, but does not send) -----
def send_with_auto_parse(text: Optional[str], max_len: int = DEFAULT_MAX_LEN) -> List[str]:
    """
    Раньше — отправляла. Теперь — подготавливает список строк (MarkdownV2) для отправки.
    Возвращает список частей (в правильном порядке). main.py отвечает за реальную отправку.
    """
    if text is None:
        return []

    # Ensure normalized (content extraction already makes MarkdownV2-safe)
    try:
        normalized = extract_content(text)
    except Exception:
        normalized = str(text or "")

    # Split into fenced segments and assemble parts trying компактно упаковать
    segments = split_fenced(normalized)
    parts = assemble_send_parts_from_segments(segments, max_len=max_len)

    # Ensure parts length limits and strip trailing whitespace
    final_parts = []
    for p in parts:
        if len(p) > 4096:
            # hard clip as last resort
            final_parts.append(p[:4096])
        else:
            final_parts.append(p)
    return final_parts


# ----- Inline preparation: try to fit into a single message -----
def prepare_inline_response(text: Optional[str], bot_username: Optional[str] = None, max_len: int = DEFAULT_MAX_LEN) -> Tuple[str, Optional[telebot.types.InlineKeyboardMarkup]]:
    """
    Для inline-ответа: пытаемся уложить весь ответ в один подготовленный кусок.
    - Если результат send_with_auto_parse даёт ровно 1 часть -> возвращаем её и клавиатуру кнопки с ссылкой на бота.
    - Если частей > 1 -> возвращаем сообщение-подсказку "не влезло" и клавиатуру (открыть бота).
    Возвращает: (text_for_inline, keyboard_or_None)
    """
    if text is None:
        text = ""

    parts = send_with_auto_parse(text, max_len=max_len)
    # Prepare keyboard if username provided
    kb = None
    if bot_username:
        try:
            kb = telebot.types.InlineKeyboardMarkup()
            kb.add(telebot.types.InlineKeyboardButton(text="Открыть бота", url=f"https://t.me/{bot_username.lstrip('@')}"))
        except Exception:
            kb = None

    if not parts:
        return "", kb

    if len(parts) == 1:
        return parts[0], kb

    # If more than 1 part — inline must not return multiple messages:
    hint = "Извините — ответ не влез в одно сообщение. Задайте запрос напрямую боту."
    return hint, kb


# ----------------- Utility: wrapping formulas -----------------
def _is_formula_like_line(line: str) -> bool:
    """
    Простейшее эвристическое определение линии как формулы/хим.реакции.
    """
    if not line or line.strip() == "":
        return False
    s = line.strip()

    # If contains clear reaction/math signs or LaTeX math commands
    if re.search(r'(\\frac|\\sqrt|\\rightarrow|\\to|->|→|↑|↓|⇌|↔|=>|⇒|=|\^|_\{|\+)', s):
        # Also ensure there are chemical tokens or digits or math operators
        chem_tokens = re.findall(r'[A-Z][a-z]?\d*', s)
        if len(chem_tokens) >= 2 or re.search(r'[\d\+\-*/=↑↓→⇌]', s):
            return True

    # Also catch common chemical arrows like "SO2 ↑" or "CO2↑"
    if re.search(r'[A-Za-z0-9]+\s*↑', s) or re.search(r'[A-Za-z0-9]+\s*↓', s):
        return True

    return False


def wrap_formulas_in_codeblocks(text: str) -> str:
    """
    Находит последовательные линии, похожие на формулы/реакции, и оборачивает их в ``` ``` блок.
    Сохраняет уже существующие fenced-блоки.
    """
    # Если уже есть ``` в тексте — split_fenced в normalize_for_markdownv2 позже сохранит их,
    # но до этого шага нам нужно работать с оригиналом (до дальнейшей нормализации).
    lines = text.splitlines()
    out_lines = []
    buf = []
    for ln in lines:
        if _is_formula_like_line(ln):
            buf.append(ln)
        else:
            if buf:
                block = "\n".join(buf).strip()
                # Ensure single empty line before/after block for readability
                out_lines.append("```")
                out_lines.append(block)
                out_lines.append("```")
                buf = []
            out_lines.append(ln)
    if buf:
        block = "\n".join(buf).strip()
        out_lines.append("```")
        out_lines.append(block)
        out_lines.append("```")
    return "\n".join(out_lines)
