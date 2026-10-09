"""Text interface for My Jarvis."""

from jarvis.ollama_client import OllamaClient, OllamaError


def handle_request(prompt: str, client: OllamaClient) -> str:
    """Validate a request and forward it to the AI client."""
    prompt = prompt.strip()

    if not prompt:
        return "Scrivi una richiesta per iniziare."

    try:
        return client.chat(prompt)
    except OllamaError as error:
        return f"Errore: {error}"


def read_multiline_request() -> str:
    """Collect lines until the user submits or cancels the request."""
    print("Jarvis > Incolla il testo su più righe.")
    print("Jarvis > Scrivi '/send' su una riga separata per inviare.")
    print("Jarvis > Scrivi '/cancel' per annullare.")

    lines: list[str] = []

    while True:
        line = input()

        if line.strip() == "/send":
            return "\n".join(lines)

        if line.strip() == "/cancel":
            return ""

        lines.append(line)


def main() -> None:
    """Run an interactive text session with a local AI model."""
    client = OllamaClient()

    print("Jarvis | Interfaccia testuale")
    print(f"Modello: {client.model}")
    print("Scrivi '/reset' per cancellare la cronologia.")
    print("Scrivi '/paste' per inserire codice o errori su più righe.")
    print("Scrivi 'esci' per terminare.\n")

    while True:
        try:
            prompt = input("Tu > ").strip()

            if prompt.lower() in {"esci", "exit", "quit"}:
                print("Jarvis > A presto!")
                break

            if prompt.lower() == "/reset":
                client.reset_history()
                print("Jarvis > Cronologia cancellata.\n")
                continue

            if prompt.lower().startswith("/paste "):
                print(
                    "Jarvis > Scrivi '/paste' da solo e premi Invio, "
                    "poi incolla il testo.\n"
                )
                continue

            if prompt.lower() == "/paste":
                prompt = read_multiline_request()

                if not prompt.strip():
                    print("Jarvis > Inserimento annullato o vuoto.\n")
                    continue

            if prompt:
                print("Jarvis > Elaborazione in corso...")

            response = handle_request(prompt, client)
            print(f"Jarvis > {response}\n")

        except (EOFError, KeyboardInterrupt):
            print("\nJarvis > Sessione terminata.")
            break


if __name__ == "__main__":
    main()