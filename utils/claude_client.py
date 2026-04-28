import asyncio
import base64
import subprocess
import tempfile
import os
from typing import Optional


async def call_claude(
    prompt: str,
    system: str = "",
    pdf_bytes: Optional[bytes] = None,
    max_tokens: int = 4096,
) -> str:
    full_prompt = f"{system}\n\n{prompt}" if system else prompt

    if pdf_bytes:
        # PDFを一時ファイルに書き出してpdfplumberでテキスト化してから渡す
        import pdfplumber, io
        text_parts = []
        try:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for page in pdf.pages:
                    t = page.extract_text() or ""
                    if t:
                        text_parts.append(t)
                    for table in page.extract_tables():
                        if table:
                            for row in table:
                                text_parts.append(" | ".join(str(c) if c else "" for c in row))
        except Exception:
            pass
        raw_text = "\n".join(text_parts)[:30000]
        full_prompt = f"{full_prompt}\n\n--- PDF抽出テキスト ---\n{raw_text}"

    result = await asyncio.to_thread(
        _run_claude_cli, full_prompt
    )
    return result


def _run_claude_cli(prompt: str) -> str:
    proc = subprocess.run(
        ["claude", "-p", prompt],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"claude CLI エラー: {proc.stderr[:300]}")
    return proc.stdout.strip()


async def call_claude_text(
    prompt: str,
    system: str = "",
    max_tokens: int = 4096,
) -> str:
    return await call_claude(prompt, system=system, max_tokens=max_tokens)
