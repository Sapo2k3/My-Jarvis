# My Jarvis

A modular AI assistant for the workbench and software development.

## Goal

Provide text and voice interaction, recognize electronic components
through a camera, and assist with programming and debugging.

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

## Current Status

The text-based assistant is operational and connected to a local
Ollama instance using `qwen2.5-coder:3b`.

Implemented features:

- Text-based interaction.
- Local AI model integration.
- Bounded, session-only conversation history.
- Conversation reset with `/reset`.
- Multiline input with `/paste`, `/send`, and `/cancel`.
- Automated tests for the CLI and HTTP client.
- Read-only analysis of explicitly selected project files with `/file`.
- File preview and explicit confirmation before model submission.
- Project-root restrictions, file-type filtering, and size limits.
- Isolated AI conversations for file analysis.
- Automated tests for file access restrictions and submission approval.

The assistant does not read project files, modify files, or execute
generated code.
## Roadmap

- [x] Text interface
- [x] AI model integration
- [x] Error handling and automated tests
- [x] Coding Agent with selected project files as context
- [ ] Log analysis and proposed diffs
- [ ] Voice input and output
- [ ] Computer Vision
- [ ] Controlled execution sandbox
- [ ] Raspberry Pi deployment and validation

## Security Principles

- Generated code must not run automatically.
- File changes require explicit approval.
- API keys and passwords must never be committed.
- Private images, recordings, and logs must remain outside version control.
