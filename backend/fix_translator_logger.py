# Fix logger.METHOD("msg", module=LogModule.TRANS) -> logger.METHOD(LogModule.TRANS, "msg") in translator and related modules.
import re
import os

base = "translator/ai_translator"
files = [
    "docx_translator.py", "xlsx_translator.py", "pptx_translator.py", "md_translator.py",
    "json_translator.py", "txt_translator.py", "srt_translator.py", "qt_ts_translator.py",
    "html_translator.py", "epub_translator.py",
]

def fix_file(path: str) -> int:
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    original = content
    # Single-line: self.logger.LEVEL("msg", module=LogModule.TRANS) or with exc_info=True
    def repl(m):
        prefix, msg, exc, _ = m.groups()
        if exc:
            return f"{prefix}(LogModule.TRANS, {msg}, exc_info=True)"
        return f"{prefix}(LogModule.TRANS, {msg})"
    content = re.sub(
        r'(self\.logger\.(?:debug|info|warning|error)\()([^,]+(?:,[^,]+)*?),(\s*exc_info=True,)?\s*module=LogModule\.TRANS\)',
        repl,
        content,
    )
    # Same for logger. (no self)
    content = re.sub(
        r'(logger\.(?:debug|info|warning|error)\()([^,]+(?:,[^,]+)*?),(\s*exc_info=True,)?\s*module=LogModule\.TRANS\)',
        repl,
        content,
    )
    # Multi-line: ... "msg",\n    module=LogModule.TRANS\n) -> ... LogModule.TRANS,\n    "msg"\n)
    content = re.sub(
        r'(self\.logger\.(?:debug|info|warning|error)\(\s*\n\s+)(.+?)(,\s*\n\s*(?:exc_info=True,?\s*\n\s*)?module=LogModule\.TRANS\s*\))',
        lambda m: m.group(1) + "LogModule.TRANS,\n    " + m.group(2).replace("\n    ", "\n    ", 1) if "\n" in m.group(2) else m.group(1) + "LogModule.TRANS, " + m.group(2) + "\n    )",
        content,
        flags=re.DOTALL,
    )
    # Simpler multiline: replace ", module=LogModule.TRANS\n..." with "\n..."
    content = re.sub(
        r',\s*\n\s*module=LogModule\.TRANS\s*\)',
        '\n    )',
        content,
    )
    content = re.sub(
        r',\s*\n\s*exc_info=True,?\s*\n\s*module=LogModule\.TRANS\s*\)',
        ',\n    exc_info=True\n    )',
        content,
    )
    # Now add LogModule.TRANS after self.logger.LEVEL( for any remaining that we just removed module=
    # (if the call has multiple lines and we removed the module= line we need to insert LogModule.TRANS, after the (
    def add_module(m):
        return m.group(1) + "LogModule.TRANS,\n    " + m.group(2)
    content = re.sub(
        r'(self\.logger\.(?:debug|info|warning|error)\(\s*\n)(\s+)(?=[f"\'])',
        add_module,
        content,
    )
    if content != original:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return 1
    return 0

os.chdir(os.path.dirname(os.path.abspath(__file__)))
n = 0
for f in files:
    path = os.path.join(base, f)
    if os.path.exists(path):
        n += fix_file(path)
print("Files modified:", n)
