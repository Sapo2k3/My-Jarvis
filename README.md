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

Initial project setup.
The AI model is not connected yet.

## Roadmap

- [ ] Text interface
- [ ] AI model integration
- [ ] Error handling and automated tests
- [ ] Coding Agent with selected project files as context
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
