"""
LLM analysis: ask Ollama to name and categorize a file.

The model is only ever trusted to make a *decision* (a name string and
a category string). Python owns every actual filesystem operation —
see validator.py and file_manager.py. This module never touches disk.
"""

import json
import logging

import ollama

import config

logger = logging.getLogger("file_segregator")

_PROMPT_TEMPLATE = """You are a file organization assistant.

Look at the original filename and the extracted content below, then decide:

1. A short, descriptive filename made of EXACTLY THREE WORDS (Title Case,
   no punctuation, no file extension, no underscores).
2. The single best-fitting category from this exact list: {categories}

Base your answer only on what is actually in the content and filename below.
Do not invent details that aren't there. If the content is empty or
unreadable, make a reasonable guess from the filename alone, and if you
truly cannot tell, use the category "Other".

Respond with ONLY a JSON object in this exact shape, nothing else:
{{"name": "Three Word Name", "category": "OneOfTheCategories"}}

Original filename: {filename}

File content:
{content}
"""


def analyze_file_with_llm(filename: str, content: str) -> dict:
    """
    Ask the local LLM for a {"name": ..., "category": ...} decision.

    Always returns a dict with "name" and "category" keys, falling
    back to safe defaults on any error, so the pipeline never breaks
    here — bad output just gets re-validated and defaulted downstream.
    """
    truncated_content = content[: config.MAX_CONTENT_CHARS]
    prompt = _PROMPT_TEMPLATE.format(
        categories=", ".join(config.CATEGORIES),
        filename=filename,
        content=truncated_content or "(no readable text found)",
    )

    try:
        response = ollama.chat(
            model=config.LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            # Ask Ollama to constrain sampling to valid JSON rather than
            # relying purely on prompt instructions ("structured output").
            format="json",
            options={"temperature": 0.2},
        )
        raw = response["message"]["content"].strip()
        result = json.loads(raw)

        if not isinstance(result, dict):
            raise ValueError("LLM did not return a JSON object")

        return {
            "name": str(result.get("name", "")),
            "category": str(result.get("category", "")),
        }

    except json.JSONDecodeError as error:
        logger.warning("LLM returned invalid JSON for %s: %s", filename, error)
    except Exception as error:
        # Covers Ollama connection errors, missing model, timeouts, etc.
        logger.warning("LLM analysis failed for %s: %s", filename, error)

    return {"name": config.FALLBACK_NAME, "category": config.FALLBACK_CATEGORY}
