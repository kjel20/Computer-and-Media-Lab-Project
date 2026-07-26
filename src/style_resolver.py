import copy
import json
import logging
import re
from pathlib import Path
from typing import Any
from config import (
    DEFAULT_FALLBACK_FONT,
    DEFAULT_STYLE_OVERRIDES,
    RESOLVED_STYLE_PROFILE_FILENAME,
    STYLE_FALLBACKS,
    STYLE_OVERRIDE_FILENAME,
    STYLE_PROFILES_DIR,
)

logger = logging.getLogger(__name__)

class StyleProfileResolver:
    """Validates detected styles and safely applies fallback values and overrides."""

    def __init__(self, profiles_dir: Path = STYLE_PROFILES_DIR) -> None:
        self.profiles_dir = Path(profiles_dir)
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

    def resolve(self, detected_profile: dict[str, Any], overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        if not isinstance(detected_profile, dict):
            raise TypeError("Detected style profile must be a dictionary.")

        resolved = self._deep_merge(copy.deepcopy(STYLE_FALLBACKS), detected_profile)
        resolved = self._validate_profile(resolved)

        active_overrides = DEFAULT_STYLE_OVERRIDES if overrides is None else overrides
        if not isinstance(active_overrides, dict):
            raise TypeError("Style overrides must be a dictionary.")

        resolved = self._deep_merge(resolved, active_overrides)
        resolved = self._validate_profile(resolved)
        resolved = self._enforce_heading_hierarchy(resolved)

        resolved["profile_version"] = detected_profile.get("profile_version", 1)
        resolved["source_files"] = detected_profile.get("source_files", [])
        resolved["source_file_count"] = detected_profile.get("source_file_count", 0)
        resolved["common_colors"] = detected_profile.get("common_colors", [])
        resolved["analysis"] = detected_profile.get("analysis", {})
        resolved["resolution"] = {
            "fallbacks_applied": True,
            "manual_overrides_applied": bool(active_overrides),
        }

        logger.info("Detected style profile validated and resolved.")
        return resolved

    def save_resolved_profile(self, profile: dict[str, Any], filename: str = RESOLVED_STYLE_PROFILE_FILENAME) -> Path:
        return self._save_json(profile, filename)

    def save_overrides(self, overrides: dict[str, Any], filename: str = STYLE_OVERRIDE_FILENAME) -> Path:
        if not isinstance(overrides, dict):
            raise TypeError("Style overrides must be a dictionary.")
        return self._save_json(overrides, filename)

    def load_overrides(self, path: Path | None = None) -> dict[str, Any]:
        path = Path(path or self.profiles_dir / STYLE_OVERRIDE_FILENAME)
        if not path.exists():
            logger.info("No saved override file found. Using configured defaults.")
            return copy.deepcopy(DEFAULT_STYLE_OVERRIDES)
        return self._load_json(path)

    def load_profile(self, path: Path) -> dict[str, Any]:
        return self._load_json(Path(path))

    def _deep_merge(self, base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
        """Merge nested dictionaries without removing fields absent from the override."""

        result = copy.deepcopy(base)

        for key, value in updates.items():
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = copy.deepcopy(value)

        return result

    def _validate_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        profile = copy.deepcopy(profile)
        profile["page"] = self._validate_page(profile.get("page", {}))
        profile["body"] = self._validate_text_style(profile.get("body", {}), "body")
        profile["title"] = self._validate_text_style(profile.get("title", {}), "title")

        for heading in ("heading_1", "heading_2", "heading_3"):
            profile[heading] = self._validate_text_style(profile.get(heading, {}), heading)

        profile["bullet"] = self._validate_bullet(profile.get("bullet", {}))
        return profile

    def _validate_page(self, page: dict[str, Any]) -> dict[str, Any]:
        fallback = STYLE_FALLBACKS["page"]
        page = self._deep_merge(fallback, page if isinstance(page, dict) else {})

        page["width"] = self._number(page.get("width"), fallback["width"], 300, 1000)
        page["height"] = self._number(page.get("height"), fallback["height"], 400, 1500)

        maximum_margin = min(page["width"], page["height"]) * 0.30
        for key in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
            page[key] = self._number(page.get(key), fallback[key], 0, maximum_margin)

        return page

    def _validate_text_style(self, style: dict[str, Any], style_name: str) -> dict[str, Any]:
        fallback = STYLE_FALLBACKS[style_name]
        style = self._deep_merge(fallback, style if isinstance(style, dict) else {})

        style["font"] = self._font(style.get("font"), fallback["font"])
        style["font_size"] = self._number(style.get("font_size"), fallback["font_size"], 6, 40)
        style["bold"] = self._boolean(style.get("bold"), fallback.get("bold", False))
        style["italic"] = self._boolean(style.get("italic"), fallback.get("italic", False))
        style["color"] = self._color(style.get("color"), fallback.get("color", "#000000"))

        for key in ("spacing_before", "spacing_after", "paragraph_spacing_before", "paragraph_spacing_after"):
            if key in style or key in fallback:
                style[key] = self._number(style.get(key), fallback.get(key, 0), 0, 72)

        if style_name == "body":
            style["line_spacing_points"] = self._number(
                style.get("line_spacing_points"), fallback["line_spacing_points"], style["font_size"], 50
            )
            style["line_spacing_ratio"] = self._number(
                style.get("line_spacing_ratio"), fallback["line_spacing_ratio"], 1.0, 3.0
            )

        if style_name == "title":
            valid_alignments = {"left", "center", "right", "justify"}
            if style.get("alignment") not in valid_alignments:
                style["alignment"] = fallback.get("alignment", "left")

        return style

    def _validate_bullet(self, bullet: dict[str, Any]) -> dict[str, Any]:
        fallback = STYLE_FALLBACKS["bullet"]
        bullet = self._deep_merge(fallback, bullet if isinstance(bullet, dict) else {})

        bullet["font"] = self._font(bullet.get("font"), fallback["font"])
        bullet["font_size"] = self._number(bullet.get("font_size"), fallback["font_size"], 6, 40)
        bullet["color"] = self._color(bullet.get("color"), fallback["color"])

        for key in ("indent_left", "hanging_indent", "nested_indent_increment", "spacing_after"):
            bullet[key] = self._number(bullet.get(key), fallback[key], 0, 200)

        if bullet["hanging_indent"] > bullet["indent_left"]:
            logger.warning("Bullet hanging indent exceeded left indent; fallback value used.")
            bullet["hanging_indent"] = fallback["hanging_indent"]

        return bullet

    def _enforce_heading_hierarchy(self, profile: dict[str, Any]) -> dict[str, Any]:
        """Ensure title > Heading 1 > Heading 2 >= Heading 3 >= body."""

        profile = copy.deepcopy(profile)
        body_size = profile["body"]["font_size"]

        minimums = {
            "heading_3": body_size,
            "heading_2": body_size + 1,
            "heading_1": body_size + 3,
            "title": body_size + 5,
        }

        profile["heading_3"]["font_size"] = max(profile["heading_3"]["font_size"], minimums["heading_3"])
        profile["heading_2"]["font_size"] = max(
            profile["heading_2"]["font_size"],
            profile["heading_3"]["font_size"] + 1,
            minimums["heading_2"],
        )
        profile["heading_1"]["font_size"] = max(
            profile["heading_1"]["font_size"],
            profile["heading_2"]["font_size"] + 1,
            minimums["heading_1"],
        )
        profile["title"]["font_size"] = max(
            profile["title"]["font_size"],
            profile["heading_1"]["font_size"] + 1,
            minimums["title"],
        )

        return profile

    def _number(self, value: Any, fallback: float, minimum: float, maximum: float) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return float(fallback)

        if not minimum <= number <= maximum:
            logger.warning("Invalid numeric style value %r; fallback %s used.", value, fallback)
            return float(fallback)

        return round(number, 2)

    def _font(self, value: Any, fallback: str) -> str:
        if not isinstance(value, str) or not value.strip():
            return fallback or DEFAULT_FALLBACK_FONT
        return value.strip()

    def _boolean(self, value: Any, fallback: bool) -> bool:
        return value if isinstance(value, bool) else fallback

    def _color(self, value: Any, fallback: str) -> str:
        if isinstance(value, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", value.strip()):
            return value.strip().upper()
        return fallback.upper()

    def _save_json(self, data: dict[str, Any], filename: str) -> Path:
        if not isinstance(data, dict):
            raise TypeError("JSON data must be a dictionary.")

        filename = filename.strip()
        if not filename:
            raise ValueError("Filename cannot be empty.")
        if not filename.lower().endswith(".json"):
            filename += ".json"

        path = self.profiles_dir / filename

        try:
            path.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8")
        except OSError as error:
            raise RuntimeError(f"Could not save JSON file: {path}") from error

        logger.info("Saved style data to %s.", path)
        return path

    def _load_json(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            raise FileNotFoundError(f"JSON file does not exist: {path}")
        if not path.is_file():
            raise ValueError(f"JSON path is not a file: {path}")

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid JSON file: {path}") from error
        except OSError as error:
            raise RuntimeError(f"Could not read JSON file: {path}") from error

        if not isinstance(data, dict):
            raise ValueError("The JSON root value must be an object.")

        return data