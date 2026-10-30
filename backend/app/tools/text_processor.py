import re
import unicodedata

from app.tools.input_errors import InputProcessingError


MAX_TEXT_CHARACTERS = 100_000


def normalize_text(
    text: str,
    *,
    allow_empty: bool = False,
    max_characters: int | None = MAX_TEXT_CHARACTERS
) -> str:
    """
    Normalize text while preserving meaningful
    line structure.

    Operations:
    1. Unicode normalization.
    2. Normalize line endings.
    3. Remove null and unwanted control characters.
    4. Normalize excessive horizontal whitespace.
    5. Collapse excessive blank lines.
    6. Enforce character limits.
    """

    if not isinstance(text, str):
        raise InputProcessingError(
            422,
            "Input text must be a string."
        )

    # Standardize Unicode.
    text = unicodedata.normalize("NFC", text)

    # Normalize line endings.
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    # Normalize non-breaking spaces.
    text = text.replace("\u00a0", " ")

    # Remove control characters except tab/newline.
    cleaned = "".join(
        char
        for char in text
        if char in "\n\t"
        or unicodedata.category(char) != "Cc"
    )

    # Normalize horizontal whitespace per line.
    lines = []

    for line in cleaned.split("\n"):

        line = re.sub(
            r"[ \t]+",
            " ",
            line
        )

        lines.append(line.strip())

    cleaned = "\n".join(lines)

    # Collapse excessive blank lines.
    cleaned = re.sub(
        r"\n{3,}",
        "\n\n",
        cleaned
    ).strip()

    if not cleaned and not allow_empty:

        raise InputProcessingError(
            422,
            "The supplied text is empty."
        )

    if (
        max_characters is not None
        and len(cleaned) > max_characters
    ):

        raise InputProcessingError(
            413,
            f"Text exceeds the maximum allowed "
            f"limit of {max_characters} characters."
        )

    return cleaned