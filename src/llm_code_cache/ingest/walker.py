from pathlib import Path


def walk_the_file_path(file_path: str) -> list[Path]:
    relevant_files: list[Path] = []
    for path in Path(file_path).rglob("*"):
        if is_relevant_file(path):
            relevant_files.append(path)
    return relevant_files


def is_relevant_file(candidate_path: Path):
    return True
