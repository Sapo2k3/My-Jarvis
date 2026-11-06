# My Jarvis

A modular AI assistant for the workbench and software development.

## Goal

Provide text and voice interaction, recognize electronic components
through a camera, and assist with programming and debugging.

Voice, Computer Vision, and controlled execution are planned features,
not currently implemented.

## Planned Architecture

- Core: request handling and response coordination.
- AI Client: connection to a local model or an external AI service.
- Coding Agent: analysis of selected project files, code generation,
  and proposed fixes.
- Voice: speech recognition and text-to-speech.
- Vision: image capture and component recognition.
- Sandbox: optional, controlled execution of code and tests.

## First Milestone

Build a text interface that sends a request to an AI model
and displays its response.

This milestone is complete.

## Current Status

The text-based assistant is operational and connected to a local
Ollama instance using `qwen2.5-coder:3b`.

Implemented features:

- Text-based interaction.
- Local AI model integration.
- Bounded, session-only conversation history.
- Conversation reset with `/reset`.
- Multiline input with `/paste`, `/send`, and `/cancel`.
- Read-only analysis of explicitly selected project files with `/file`.
- File preview and explicit confirmation before model submission.
- Project-root restrictions, file-type filtering, and size limits.
- Dedicated AI clients for file analysis and debugging, separate from
  the main conversation.
- Combined source and error-log analysis with `/debug`.
- Read-only validation of model-generated, single-file unified diffs
  in the `/debug` workflow.
- At most one automatic revision request after a rejected patch,
  subject to a revision-prompt size limit.
- Separate reporting of initial and revised patch-validation results.
- Automated tests for the CLI, HTTP client, file access restrictions,
  submission approval, patch validation, and revision orchestration.
- An integration test using real Git validation to check that the
  selected source file remains unchanged during patch revision.

The assistant reads only explicitly selected files through the
restricted file reader. It does not scan the repository automatically,
apply patches, or execute generated code.

Conversation history is stored only in memory and is lost when the
application exits. Persistent memory is not implemented.

## Running the Assistant

Run the application from the project root:

```bash
PYTHONPATH=src python -m jarvis.main
```

Ollama must be running locally with `qwen2.5-coder:3b` available.
The client uses `http://localhost:11434/api/chat`.

The working directory at startup becomes the authorized root for
selected-file access.

### Available Commands

- `/reset`: clear the main conversation history.
- `/paste`: enter a multiline request.
- `/file`: preview and analyze a selected project file.
- `/debug`: analyze a selected file together with an error log.
- `esci`, `exit`, or `quit`: close the session.

In multiline mode, enter `/send` on a separate line to submit the
content, or `/cancel` to cancel.

## Debugging and Patch Validation

The `/debug` workflow previews the selected source and error log
before requesting explicit approval to send them to the local model.

Model responses may contain incorrect explanations, unsupported
formatting, or invalid diffs. Prompt compliance is not guaranteed.

When a recognized diff is present, the local validator restricts it
to the selected file and checks it against a temporary copy of the
analyzed source using `git apply --check`.

The patch is never applied.

Validation statuses:

- `NO_PATCH`: no recognized Markdown `diff` block was found.
- `REJECTED`: the patch format is unsupported, the target is not
  allowed, or Git rejected the patch.
- `CHECK_ERROR`: validation could not be completed, for example
  because Git is unavailable or the check timed out.
- `APPLICABLE`: the patch applies to the analyzed source snapshot.

`APPLICABLE` does not prove that the bug is fixed, the behavior is
correct, the code is safe, or tests pass. It does not authorize
applying the patch or guarantee applicability if the source changes
after analysis.

Patch validation is currently integrated with `/debug`, not `/file`.

### Bounded Patch Revision

If the first patch is `REJECTED`, Jarvis may request one revision from
the local model. The initial confirmation explicitly covers this
optional second submission.

The revision request includes:

- The selected file path.
- The original source.
- The original error log.
- The previous model response.
- The validator's rejection diagnostic.

These values are provided as untrusted evidence, not authorized
instructions. Conversation history is cleared before the second
request to avoid duplicating the previous exchange.

The complete revision prompt is limited to 6,000 characters. If it
exceeds this limit, the revision is skipped and the reason is displayed.
No evidence is silently truncated.

This character limit is an application guardrail, not an exact token
budget or a guarantee that the request fits the model context window.

No revision is requested for `NO_PATCH` or `CHECK_ERROR`. The second
response is checked by the same validator against the original source
snapshot, and no third attempt is made.

If the second model request fails, the initial response and its
validation result are preserved.

A revision may still be rejected. Format repair and patch applicability
do not establish behavioral correctness.

## Running Tests

Run the complete test suite from the project root:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

The tests do not require a running Ollama instance. Model requests are
mocked.

Some patch-validation and integration tests use Git on temporary files.
These tests are skipped when Git is unavailable.

## Roadmap

- [x] Text interface
- [x] AI model integration
- [x] Error handling and automated tests
- [x] Coding Agent with selected project files as context
- [x] Log analysis and proposed diffs
- [x] Read-only patch validation for debugging
- [x] Bounded revision of rejected debugging patches
- [ ] Voice input and output
- [ ] Computer Vision
- [ ] Controlled execution sandbox
- [ ] Raspberry Pi deployment and validation

## Security Principles

- Generated code must not run automatically.
- Patch application and automatic source-file writes are not implemented.
- Any future file-changing workflow must require explicit approval.
- Selected content must be previewed and approved before model submission.
- File-access filters and prompt instructions are not a sandbox.
- Allowed source files may still contain credentials or private data.
- API keys and passwords must never be committed.
- Private images, recordings, and logs must remain outside version control.