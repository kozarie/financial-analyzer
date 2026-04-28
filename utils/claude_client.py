import asyncio
import io
import os
import subprocess
from typing import Optional


def _use_api() -> bool:
    """ANTHROPIC_API_KEY があればAPI、なければCLIを使う"""
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


async def call_claude(
    prompt: str,
    system: str = "",
    pdf_bytes: Optional[bytes] = None,
    max_tokens: int = 4096,
) -> str:
    if _use_api():
        return await _call_via_api(prompt, system, pdf_bytes, max_tokens)
    else:
        return await _call_via_cli(prompt, system, pdf_bytes)


async def _call_via_api(
    prompt: str,
    system: str,
    pdf_bytes: Optional[bytes],
    max_tokens: int,
) -> str:
    import anthropic, base64
    client = anthropic.AsyncAnthropic()
    content: list = []
    if pdf_bytes:
        content.append({
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": base64.standard_b64encode(pdf_bytes).decode(),
            },
        })
    content.append({"type": "text", "text": prompt})
    kwargs = {
        "model": "claude-sonnet-4-6",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": content}],
    }
    if system:
        kwargs["system"] = system
    resp = await client.messages.create(**kwargs)
    return resp.content[0].text


async def _call_via_cli(
    prompt: str,
    system: str,
    pdf_bytes: Optional[bytes],
) -> str:
    full_prompt = f"{system}\n\n{prompt}" if system else prompt

    if pdf_bytes:
        import pdfplumber
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

    return await asyncio.to_thread(_run_claude_cli, full_prompt)


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
