"""Shared date and file-safety checks for dataset builders."""
from datetime import date
from pathlib import Path


def parse_calendar_date(value: str) -> date:
    """Accept only canonical YYYY-MM-DD calendar dates, never ISO week dates."""
    try:
        parsed = date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Expected YYYY-MM-DD date, got {value!r}") from exc
    if parsed.isoformat() != value:
        raise ValueError(f"Expected YYYY-MM-DD date, got {value!r}")
    return parsed


def validate_output_paths(inputs, outputs) -> None:
    """Reject input/output and output/output aliases before any files are written."""
    inputs = [Path(p) for p in inputs]
    outputs = [Path(p) for p in outputs]

    def same_file(left, right):
        return (left.resolve() == right.resolve()
                or (left.exists() and right.exists() and left.samefile(right)))

    for index, output in enumerate(outputs):
        for other in inputs + outputs[:index]:
            if same_file(output, other):
                raise ValueError(f"Input and output files must differ; conflicting paths: {other}, {output}")
