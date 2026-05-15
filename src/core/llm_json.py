"""Defensive JSON-mode chat helpers.

Different OpenAI-compatible providers (OpenAI, DeepSeek, Azure, vLLM, ...)
honour ``response_format={"type": "json_object"}`` to different degrees. Some
reject it outright with a 400; others accept it but still return text wrapped
in ```json fences```; a few ignore it silently.

``chat_json`` tries the strict ``json_object`` mode first, then falls back to
plain completion with an explicit "return ONLY JSON" instruction and a
permissive parser that strips code fences and locates the first balanced JSON
object in the response.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Mapping

try:  # pragma: no cover - optional dependency in offline runs
	from openai import BadRequestError  # type: ignore[import]
except Exception:  # pragma: no cover
	BadRequestError = Exception  # type: ignore[assignment,misc]


_JSON_HINT = (
	"Return ONLY a single valid JSON object as your entire response. "
	"Do not wrap it in markdown code fences. Do not include any prose, "
	"commentary, or explanation before or after the JSON."
)


def chat_json(
	client: Any,
	model: str,
	messages: List[Mapping[str, str]],
	temperature: float = 0.2,
) -> Dict[str, Any]:
	"""Call ``client.chat.completions.create`` and parse the response as JSON.

	First attempt uses ``response_format={"type": "json_object"}``. On any
	failure (provider rejects the parameter, returns malformed JSON, etc.) it
	retries once with the parameter dropped and an explicit JSON-only hint
	injected into the system prompt.
	"""

	last_error: Exception | None = None

	# Attempt 1: strict json_object mode.
	try:
		response = client.chat.completions.create(
			model=model,
			temperature=temperature,
			response_format={"type": "json_object"},
			messages=list(messages),
		)
		content = response.choices[0].message.content  # type: ignore[index]
		return _parse_json_loose(content)
	except BadRequestError as exc:
		# Provider rejected response_format — fall through to plain mode.
		last_error = exc
	except (json.JSONDecodeError, ValueError) as exc:
		# Got JSON-mode response but it didn't parse — fall through.
		last_error = exc
	except Exception as exc:  # pragma: no cover - unexpected SDK errors
		last_error = exc

	# Attempt 2: plain completion with an explicit instruction.
	try:
		response = client.chat.completions.create(
			model=model,
			temperature=temperature,
			messages=_inject_hint(messages),
		)
		content = response.choices[0].message.content  # type: ignore[index]
		return _parse_json_loose(content)
	except Exception as exc:
		# Surface the most informative error.
		raise exc from last_error


def _inject_hint(messages: List[Mapping[str, str]]) -> List[Dict[str, str]]:
	"""Append the JSON-only hint to the (first) system message, or insert one."""

	out: List[Dict[str, str]] = [dict(m) for m in messages]
	for msg in out:
		if msg.get("role") == "system":
			msg["content"] = f"{msg['content']}\n\n{_JSON_HINT}"
			return out
	return [{"role": "system", "content": _JSON_HINT}, *out]


_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)
_FIRST_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_json_loose(content: str | None) -> Dict[str, Any]:
	"""Parse JSON tolerantly: strip code fences, extract first balanced object."""

	if not content:
		return {}
	stripped = content.strip()
	# Strip ```json ... ``` or ``` ... ``` fences.
	if stripped.startswith("```"):
		stripped = _FENCE_RE.sub("", stripped).strip()

	try:
		return json.loads(stripped)
	except json.JSONDecodeError:
		pass

	# Locate the first JSON object substring as a last resort.
	match = _FIRST_OBJ_RE.search(stripped)
	if match:
		return json.loads(match.group(0))

	raise json.JSONDecodeError("No JSON object found in response", stripped, 0)
