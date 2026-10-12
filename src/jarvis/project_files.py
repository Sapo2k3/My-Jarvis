"""Read explicitly selected project files with basic access restrictions."""

from pathlib import Path

class ProjectFileError(Exception):
    """Represent a rejected or unreadable project file."""
    
class ProjectFileReader:
    """Read bounded UTF-8 files within a configured project root."""
    
    ALLOWED_SUFFIXES = {
        ".py",
        ".java",
        ".js",
        ".ts",
        ".html",
        ".css",
        ".c",
        ".cpp",
        ".h",
        ".ino",
        ".md",
    }
    
    BLOCKED_DIRECTORIES = {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        "node_modules",
        "secrets",
        "models",
        "data",
        "logs",
        "recordings",
        "captures",
    }
    
    def __init__(
        self,
        root: Path,
        max_bytes: int = 8192,
    ) -> None:
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive.")
        
        self.root = root.resolve()
        self.max_bytes = max_bytes
        
        if not self.root.is_dir():
            raise ProjectFileError(
                "La cartella del progetto non è valida."
            )
            

    def _validate_relative_path(self, path:Path):
        """Reject excluded directories and unsupported file types."""
        if any(
            part.lower() in self.BLOCKED_DIRECTORIES
            for part in path.parts[:-1]
        ):
            raise ProjectFileError(
                "Il file si trova in una cartella esclusa."
            )
        if path.suffix.lower() not in self.ALLOWED_SUFFIXES:
            raise ProjectFileError(
                "Tipo di file non consentito."
            )
            
    def read(self, relative_path: str) -> str:
        """Read a selected file without modifying it."""
        if not relative_path.strip():
            raise ProjectFileError(
                "Specifica il percorso di un file."
            )
            
        requested_path = Path(relative_path)
        
        if requested_path.is_absolute():
            raise ProjectFileError(
                "Usa un percorso relativo alla cartella del progetto."
            )
            
        self._validate_relative_path(requested_path)
        
        try:
            resolved_path = (self.root / requested_path).resolve(
                strict=True
            )
        except (OSError, RuntimeError) as error:
            raise ProjectFileError(
                "Il percorso non esiste o non è accessibile."
            ) from error
            
        try:
            resolved_relative_path = resolved_path.relative_to(
                self.root
            )
        except ValueError as error:
            raise ProjectFileError(
                "Il percorso esce dalla cartella del progetto."
            ) from error
            
        self._validate_relative_path(resolved_relative_path)
        
        if not resolved_path.is_file():
            raise ProjectFileError(
                "Il percorso non indica un file."
            )
            
        try:
            with resolved_path.open("rb") as file:
                raw_content = file.read(self.max_bytes + 1)
        except OSError as error:
            raise ProjectFileError(
                "Impossibile leggere il file."
            ) from error
            
        if len(raw_content) > self.max_bytes:
            raise ProjectFileError(
                f"Il file supera il limite di {self.max_bytes} byte."
            )
            
        if b"\x00" in raw_content:
            raise ProjectFileError(
                "Il file contiene dati binari non consentiti."
            )
        
        try:
            return raw_content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ProjectFileError(
                "Il file non è un testo UTF-8 valido."
            ) from error
