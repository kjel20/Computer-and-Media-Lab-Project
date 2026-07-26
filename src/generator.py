import json
import logging
import re
from typing import Any
import httpx
import ollama
from ollama import Client
from config import (
    MAX_QUALITY_REPAIR_ATTEMPTS,
    OLLAMA_HOST,
    OLLAMA_MODEL,
    OLLAMA_NUM_PREDICT,
    OLLAMA_TEMPERATURE,
    OLLAMA_TIMEOUT_SECONDS,
)
from src.note_schema import NoteSchema
from src.content_quality import ContentQualityValidator
from src.progress import ProgressCallback, report_progress
from src.prompt_templates import (
    CONTENT_QUALITY_REPAIR_TEMPLATE,
    JSON_REPAIR_TEMPLATE,
)

logger = logging.getLogger(__name__)

class NoteGenerator:
    """Generates and validates structured lecture notes using local Ollama."""

    def __init__(
        self,
        model: str = OLLAMA_MODEL,
        host: str = OLLAMA_HOST,
        timeout_seconds: int = OLLAMA_TIMEOUT_SECONDS,
    ) -> None:
        self.model = model
        self.host = host
        self.timeout_seconds = timeout_seconds
        self.schema = NoteSchema()
        self.quality_validator = ContentQualityValidator()
        self._validate_settings()
        self.client = Client(
            host=self.host,
            timeout=self.timeout_seconds,
        )

    def generate_raw(self, prompt: str) -> str:
        """Send a prompt to Ollama and return the unparsed response text."""

        prompt = self._validate_prompt(prompt)
        return self._request(prompt)

    def generate_structured(self, prompt: str, progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
        """
        Generate, parse, validate, repair, and normalize lecture notes.

        One repair request is made when the first response is malformed
        JSON or does not follow the required note schema.
        """

        prompt = self._validate_prompt(prompt)
        report_progress(progress_callback, 70, "Waiting for the local model response")
        raw_response = self._request(prompt)

        try:
            parsed_data = self._parse_json_response(raw_response)
            valid, errors = self.schema.validate(parsed_data)

            if valid:
                normalized = self.schema.normalize(parsed_data)
                self._ensure_usable_notes(normalized)
                logger.info("First Ollama response passed schema validation.")
                report_progress(progress_callback, 78, "Model output parsed and validated")
                return normalized

            logger.warning(
                "First Ollama response failed schema validation: %s",
                "; ".join(errors),
            )

        except (ValueError, json.JSONDecodeError) as error:
            logger.warning("First Ollama response could not be parsed: %s", error)

        logger.info("Attempting one JSON repair request.")
        report_progress(progress_callback, 75, "Repairing the model JSON structure")

        repair_prompt = JSON_REPAIR_TEMPLATE.format(
            schema=self._get_schema_text(),
            invalid_response=self._limit_repair_input(raw_response),
        )

        repaired_response = self._request(repair_prompt)

        try:
            repaired_data = self._parse_json_response(repaired_response)
        except (ValueError, json.JSONDecodeError) as error:
            logger.exception("The repaired Ollama response was still invalid JSON.")
            raise ValueError(
                "Ollama returned invalid JSON, and the automatic repair attempt "
                "also failed. Try generating the notes again."
            ) from error

        valid, errors = self.schema.validate(repaired_data)

        if not valid:
            logger.warning(
                "Repaired response still had schema problems: %s",
                "; ".join(errors),
            )

        normalized = self.schema.normalize(repaired_data)
        self._ensure_usable_notes(normalized)

        logger.info("Ollama response repaired and normalized successfully.")
        report_progress(progress_callback, 79, "Repaired model output validated")
        return normalized
    
    def generate_quality_checked(
        self,
        prompt: str,
        transcript: str,
        progress_callback: ProgressCallback | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """
        Generate structured notes and validate their content quality.

        If the first result contains vague, incomplete, or placeholder
        content, a limited number of quality-repair attempts are made.
        """

        prompt = self._validate_prompt(prompt)

        if not isinstance(transcript, str) or not transcript.strip():
            raise ValueError(
                "A non-empty transcript is required for "
                "content-quality checking."
            )

        transcript = transcript.strip()

        # Generate and structurally validate the initial notes.
        notes = self.generate_structured(
            prompt,
            progress_callback=progress_callback,
        )

        quality = self.quality_validator.evaluate(
            notes=notes,
            transcript=transcript,
        )

        if quality["passed"]:
            logger.info(
                "Generated notes passed content-quality validation "
                "with score %d.",
                quality["score"],
            )

            report_progress(
                progress_callback,
                84,
                "Generated notes passed content-quality validation",
            )
            return notes, quality

        logger.warning(
            "Initial generated notes failed content-quality validation "
            "(score=%d, errors=%d, warnings=%d).",
            quality["score"],
            len(quality.get("errors", [])),
            len(quality.get("warnings", [])),
        )

        # Reuse the most recently generated notes and quality report during each repair attempt.
        current_notes = notes
        current_quality = quality

        for attempt in range(
            1,
            MAX_QUALITY_REPAIR_ATTEMPTS + 1,
        ):
            logger.warning(
                "Starting content-quality repair attempt %d of %d.",
                attempt,
                MAX_QUALITY_REPAIR_ATTEMPTS,
            )

            progress_percent = min(82 + ((attempt - 1) * 2), 85,)

            report_progress(
                progress_callback,
                progress_percent,
                (
                    "Improving weak or placeholder note content "
                    f"(attempt {attempt} of "
                    f"{MAX_QUALITY_REPAIR_ATTEMPTS})"
                ),
            )

            repair_prompt = CONTENT_QUALITY_REPAIR_TEMPLATE.format(
                quality_feedback=(
                    self.quality_validator.build_repair_feedback(
                        current_quality
                    )
                ),
                transcript=transcript,
                current_notes=json.dumps(
                    current_notes,
                    indent=2,
                    ensure_ascii=False,
                ),
                schema=self._get_schema_text(),
            )

            try:
                # generate_structured() also handles malformed JSON and performs one structural repair when necessary.
                repaired_notes = self.generate_structured(
                    repair_prompt,
                    progress_callback=None,
                )

            except (
                ValueError,
                RuntimeError,
                ConnectionError,
                TimeoutError,
            ) as error:
                logger.warning(
                    "Content-quality repair attempt %d could not produce "
                    "usable structured notes: %s",
                    attempt,
                    error,
                )

                if attempt == MAX_QUALITY_REPAIR_ATTEMPTS:
                    raise ValueError(
                        "Ollama could not produce usable notes after "
                        f"{MAX_QUALITY_REPAIR_ATTEMPTS} content-quality "
                        "repair attempts. Try generating again or use a "
                        "shorter, clearer transcript."
                    ) from error

                continue

            repaired_quality = self.quality_validator.evaluate(
                notes=repaired_notes,
                transcript=transcript,
            )

            if repaired_quality["passed"]:
                logger.info(
                    "Content-quality repair attempt %d succeeded "
                    "with score %d.",
                    attempt,
                    repaired_quality["score"],
                )

                report_progress(
                    progress_callback,
                    86,
                    "Improved notes passed content-quality validation",
                )

                return repaired_notes, repaired_quality

            logger.warning(
                "Content-quality repair attempt %d did not pass "
                "(score=%d, errors=%d, warnings=%d).",
                attempt,
                repaired_quality["score"],
                len(repaired_quality.get("errors", [])),
                len(repaired_quality.get("warnings", [])),
            )

            # The next repair attempt should improve the newest result,
            # rather than starting again from the original weak notes.
            current_notes = repaired_notes
            current_quality = repaired_quality

        raise ValueError(
            "Ollama produced structurally valid notes, but the content "
            "remained too vague, incomplete, or contained placeholders "
            f"after {MAX_QUALITY_REPAIR_ATTEMPTS} repair attempts. "
            "Try generating again or use a shorter, clearer transcript."
        )

    def check_connection(self) -> bool:
        """Return True when the local Ollama service can be reached."""

        try:
            self.client.list()
            return True
        except (
            httpx.TimeoutException,
            httpx.ConnectError,
            httpx.HTTPError,
            ollama.ResponseError,
            OSError,
        ):
            return False

    def check_model_available(self) -> bool:
        """Return True when the configured Ollama model is installed."""

        try:
            response = self.client.list()
        except httpx.TimeoutException as error:
            raise TimeoutError(
                "Ollama did not respond while checking installed models."
            ) from error
        except (httpx.ConnectError, httpx.HTTPError, OSError) as error:
            raise ConnectionError(
                "Could not connect to Ollama while checking installed models."
            ) from error

        return self.model in self._extract_model_names(response)

    def _request(self, prompt: str) -> str:
        """Make one Ollama request and return its response text."""

        logger.info("Starting Ollama generation with model %s.", self.model)

        try:
            response = self.client.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                format="json",
                stream=False,
                options={
                    "temperature": OLLAMA_TEMPERATURE,
                    "num_predict": OLLAMA_NUM_PREDICT,
                },
            )

        except ollama.ResponseError as error:
            self._handle_response_error(error)

        except httpx.TimeoutException as error:
            logger.exception(
                "Ollama request timed out after %d seconds.",
                self.timeout_seconds,
            )
            raise TimeoutError(
                "Ollama took too long to generate the notes. "
                f"The request exceeded {self.timeout_seconds} seconds. "
                "Try a shorter transcript or increase "
                "OLLAMA_TIMEOUT_SECONDS in config.py."
            ) from error

        except httpx.ConnectError as error:
            logger.exception("Could not connect to Ollama at %s.", self.host)
            raise ConnectionError(
                "Could not connect to Ollama. Make sure Ollama is running "
                f"and that OLLAMA_HOST is correct. Current host: {self.host}"
            ) from error

        except httpx.HTTPError as error:
            logger.exception("HTTP communication with Ollama failed.")
            raise ConnectionError(
                "Communication with Ollama failed. Check that the local "
                "Ollama service is running correctly."
            ) from error

        except (ConnectionError, OSError) as error:
            logger.exception("Local Ollama connection failed.")
            raise ConnectionError(
                "Could not communicate with the local Ollama service."
            ) from error

        except Exception as error:
            logger.exception("Unexpected Ollama generation failure.")
            raise RuntimeError(
                "An unexpected error occurred while generating notes with Ollama."
            ) from error

        raw_text = self._extract_response_text(response)

        logger.info(
            "Ollama generation completed. Response length: %d characters.",
            len(raw_text),
        )
        return raw_text

    def _parse_json_response(self, raw_response: str) -> dict[str, Any]:
        """
        Clean an Ollama response and parse its main JSON object.

        Handles:
        - ```json code fences;
        - ordinary ``` fences;
        - explanations before JSON;
        - explanations after JSON.
        """

        if not isinstance(raw_response, str) or not raw_response.strip():
            raise ValueError("The Ollama response was empty.")

        cleaned = self._remove_code_fences(raw_response.strip())
        json_text = self._extract_json_object(cleaned)

        try:
            parsed = json.loads(json_text)
        except json.JSONDecodeError as error:
            raise json.JSONDecodeError(
                f"Could not parse Ollama JSON: {error.msg}",
                error.doc,
                error.pos,
            ) from error

        if not isinstance(parsed, dict):
            raise ValueError(
                "The Ollama response must contain one JSON object at its root."
            )

        return parsed

    def _remove_code_fences(self, text: str) -> str:
        """Remove Markdown JSON fences when the model includes them."""

        text = text.strip()

        fenced_match = re.fullmatch(
            r"```(?:json)?\s*(.*?)\s*```",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )

        if fenced_match:
            return fenced_match.group(1).strip()

        text = re.sub(
            r"^\s*```(?:json)?\s*",
            "",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(r"\s*```\s*$", "", text)

        return text.strip()

    def _extract_json_object(self, text: str) -> str:
        """
        Extract the first complete top-level JSON object.

        Brace matching ignores braces that occur inside quoted strings.
        """

        start = text.find("{")

        if start == -1:
            raise ValueError("No JSON object was found in the Ollama response.")

        depth = 0
        inside_string = False
        escaped = False

        for index in range(start, len(text)):
            character = text[index]

            if escaped:
                escaped = False
                continue

            if character == "\\" and inside_string:
                escaped = True
                continue

            if character == '"':
                inside_string = not inside_string
                continue

            if inside_string:
                continue

            if character == "{":
                depth += 1
            elif character == "}":
                depth -= 1

                if depth == 0:
                    return text[start:index + 1]

        raise ValueError(
            "A JSON object started in the Ollama response but did not close."
        )

    def _ensure_usable_notes(self, notes: dict[str, Any]) -> None:
        """Reject normalized output that contains no meaningful note sections."""

        if not isinstance(notes, dict):
            raise ValueError("Normalized note data must be a dictionary.")

        sections = notes.get("sections", [])

        if not isinstance(sections, list) or not sections:
            raise ValueError(
                "Ollama returned no usable lecture-note sections, even after "
                "normalization. Try generating the notes again."
            )

    def _get_schema_text(self) -> str:
        """Return the expected note structure for repair requests."""

        schema_example = {
            "title": "",
            "subtitle": "",
            "sections": [
                {
                    "heading": "",
                    "paragraphs": [],
                    "bullets": [],
                    "definitions": [],
                    "examples": [],
                }
            ],
            "summary": [],
        }

        return json.dumps(
            schema_example,
            indent=2,
            ensure_ascii=False,
        )

    def _limit_repair_input(self, raw_response: str, limit: int = 12000) -> str:
        """Prevent an unexpectedly large invalid response from bloating repair."""

        if len(raw_response) <= limit:
            return raw_response

        logger.warning(
            "Invalid response exceeded %d characters and was shortened "
            "before the repair request.",
            limit,
        )

        shortened = raw_response[:limit]
        last_space = shortened.rfind(" ")
        if last_space > limit * 0.8:
            shortened = shortened[:last_space]
        return shortened.rstrip() + "\n[Invalid response truncated.]"

    def _extract_response_text(self, response: Any) -> str:
        """Extract text content from object-style or dictionary responses."""

        try:
            content = response.message.content
        except AttributeError:
            try:
                content = response["message"]["content"]
            except (KeyError, TypeError) as error:
                raise RuntimeError(
                    "Ollama returned an unexpected response format."
                ) from error

        if not isinstance(content, str):
            raise RuntimeError(
                "Ollama returned response content that was not text."
            )

        content = content.strip()

        if not content:
            raise RuntimeError(
                "Ollama returned an empty response. Try generating again "
                "or shortening the prompt."
            )
        return content

    def _extract_model_names(self, response: Any) -> set[str]:
        """Extract installed model names from an Ollama list response."""

        try:
            models = response.models
        except AttributeError:
            models = response.get("models", [])

        names = set()

        for model in models:
            try:
                name = model.model
            except AttributeError:
                name = (
                    model.get("model") or model.get("name")
                    if isinstance(model, dict)
                    else None
                )

            if isinstance(name, str) and name.strip():
                names.add(name.strip())
        return names

    def _handle_response_error(self, error: ollama.ResponseError) -> None:
        """Convert Ollama server errors into clearer application errors."""

        status_code = getattr(error, "status_code", None)
        message = str(getattr(error, "error", error))
        normalized = message.lower()

        logger.error(
            "Ollama response error. Status=%s, message=%s",
            status_code,
            message,
        )

        model_missing = (
            status_code == 404
            or (
                "model" in normalized
                and (
                    "not found" in normalized
                    or "does not exist" in normalized
                )
            )
        )

        if model_missing:
            raise RuntimeError(
                f"The Ollama model '{self.model}' is unavailable. "
                f"Install it with: ollama pull {self.model}"
            ) from error

        raise RuntimeError(
            f"Ollama could not generate the notes. Server message: {message}"
        ) from error

    def _validate_prompt(self, prompt: str) -> str:
        if not isinstance(prompt, str):
            raise TypeError("The Ollama prompt must be a string.")

        prompt = prompt.strip()

        if not prompt:
            raise ValueError("The Ollama prompt cannot be empty.")
        return prompt

    def _validate_settings(self) -> None:
        if not isinstance(self.model, str) or not self.model.strip():
            raise ValueError("Ollama model name must be a non-empty string.")

        if not isinstance(self.host, str) or not self.host.strip():
            raise ValueError("Ollama host must be a non-empty string.")

        if not self.host.startswith(("http://", "https://")):
            raise ValueError(
                "Ollama host must begin with http:// or https://."
            )

        if not isinstance(self.timeout_seconds, int):
            raise TypeError("Ollama timeout must be an integer.")

        if self.timeout_seconds <= 0:
            raise ValueError("Ollama timeout must be greater than zero.")
