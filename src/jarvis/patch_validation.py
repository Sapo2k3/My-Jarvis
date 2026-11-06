"""Validate a single-file unified diff without applying it."""

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory

@dataclass(frozen=True)
class PatchCheck:
    """Describe patch applicability, not behavioral correctness."""
    
    status: str
    detail: str
    
def _normalize_patch(patch: str, selected_path: str) -> str:
    """Restrict a patch to one file and remap it to a temporary snapshot."""
    path = PurePosixPath(selected_path)
    
    if (
        path.is_absolute()
        or ".." in path.parts
        or not path.parts
        or "\\" in selected_path
        or any(character.isspace() for character in selected_path)
    ):
        raise ValueError(
            "Percorso no nsupportato dal validatore iniziale."
        )
        
    expected_path = path.as_posix()
    lines = patch.splitlines()
    
    if lines and lines[0].startswith("diff --git "):
        expected_header = (
            f"diff --git a/{expected_path} b/{expected_path}"
        )
        if lines.pop(0) != expected_header:
            raise ValueError("Il diff non riguarda il file selezionato.")
        
    if lines and lines[0].startswith("index "):
        index_line = lines.pop(0)

        if not re.fullmatch(
            r"index [0-9a-f]+\.\.[0-9a-f]+(?: 100644| 100755)?",
            index_line,
        ):
            raise ValueError("Metadati index non supportati.")
        
    if len(lines) < 3:
        raise ValueError("Diff incompleto.")
    
    if lines[0] != f"--- a/{expected_path}":
        raise ValueError("Percorso originale non consentito.")
    
    if lines[1] != f"+++ b/{expected_path}":
        raise ValueError("Percorso di destinazione non consentito.")
    
    body = lines[2:]
    seen_hunk = False
    seen_change = False
    
    for line in body:
        if line.startswith("@@ "):
            if not re.fullmatch(
                r"@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@.*",
                line,
            ):
                raise ValueError("Intestazione del blocco non valida.")
            seen_hunk = True
            continue
        
        if not seen_hunk:
            raise ValueError("Contenuto fuori da un blocco diff.")
        
        if line.startswith(("--- ", "+++ ")):
            raise ValueError("Diff multiplo o contenuto ambiguo non supportato")
        
        if line == r"\ No newline at end of file":
            continue
        
        if not line or line[0] not in " +-":
            raise ValueError("Riga diff non valida.")
        
        if line[0] in "+-":
            seen_change = True
            
    if not seen_hunk or not seen_change:
        raise ValueError("Il diff non contiene modifiche verificabili.")
    
    return (
        "--- a/selected.txt\n"
        "+++ b/selected.txt\n"
        + "\n".join(body)
        + "\n"
    )
    
def validate_model_patch(
    response: str,
    selected_path: str,
    source: str,
) -> PatchCheck:
    """Check a model-generated patch against the source snapshot."""
    blocks = re.findall(
        r"^```diff[ \t]*\r?\n(.*?)^```[ \t]*\r?$",
        response,
        flags=re.MULTILINE | re.DOTALL,
    )

    if not blocks:
        return PatchCheck(
            "NO_PATCH",
            "Nessun blocco Markdown 'diff' riconosciuto.",
        )

    if len(blocks) != 1:
        return PatchCheck(
            "REJECTED",
            "È richiesto un solo blocco diff.",
        )

    if len(blocks[0]) > 50000:
        return PatchCheck(
            "REJECTED",
            "Diff troppo grande.",
        )
        
    try:
        normalized = _normalize_patch(blocks[0], selected_path)
    except ValueError as error:
        return PatchCheck("REJECTED", str(error))
    
    try:
        with TemporaryDirectory(prefix = "jarvis-patch-") as directory:
            snapshot = Path(directory) / "selected.txt"
            snapshot.write_bytes(source.encode("utf-8"))
            
            result = subprocess.run(
                [
                    "git",
                    "apply",
                    "--check",
                    "--whitespace=nowarn",
                    "-",
                ],
                input = normalized,
                text = True,
                encoding = "utf-8",
                errors = "replace",
                capture_output = True,
                cwd = directory,
                timeout = 5,
                shell = False,
            )
    except FileNotFoundError:
        return PatchCheck(
            "CHECK_ERROR",
            "Git non è disponibile.",
        )
    except subprocess.TimeoutExpired:
        return PatchCheck(
            "CHECK_ERROR",
            "Timeout durante la verifica Git."
        )
    except OSError as error:
        return PatchCheck(
            "CHECK_ERROR",
            f"Verifica non disponibile: {error}",
        )
    
    if result.returncode != 0:
        detail = result.stderr.strip() or "Git ha rifiutato il diff."
        return PatchCheck("REJECTED", detail[:1500])
    
    return PatchCheck(
        "APPLICABLE",
        "Il diff è applicabile alla copia del contenuto analizzato."
        "La correttezza del comportamento non è stata verificata",
    )
