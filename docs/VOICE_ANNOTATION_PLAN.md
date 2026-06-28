# Voice Annotation Plan

This plan adds optional cloud-backed voice input to Terminal Annotator. Voice is a faster input method for a terminal comment; selected terminal text is optional context, and standalone comments are valid when no text is selected.

## Decision

Use LiteLLM as the first transcription abstraction.

Reasons:

- LiteLLM supports audio transcription through `/audio/transcriptions`.
- It provides one Python-facing abstraction across multiple transcription providers.
- It supports provider routing patterns such as fallbacks, logging, load balancing, and proxy deployment.
- It keeps Terminal Annotator independent from a single speech-to-text vendor.

The first implementation should use the LiteLLM Python SDK directly. The design should also allow a LiteLLM proxy later for centralized API keys, routing, spend controls, and team configuration.

Reference:

- https://docs.litellm.ai/docs/audio_transcription

Implementation reference:

- https://github.com/MervinPraison/PraisonAI/blob/main/src/praisonai/praisonai/capabilities/audio.py

Adopt its small-wrapper pattern: lazy LiteLLM import, a typed transcription result, path/file handling, optional provider parameters, and explicit response normalization. Do not adopt its text-to-speech surface for this feature.

## User Workflow

1. User opens `New terminal comment`.
2. If terminal text is selected, the dialog shows it as context.
3. Dialog focuses the comment editor.
4. User clicks `Record`.
5. Dialog records microphone audio without blocking GTK.
6. User clicks `Stop`.
7. Dialog sends the audio file to LiteLLM transcription in a background worker.
8. Transcript is inserted into the existing comment text box.
9. User edits the transcript if needed.
10. User saves the comment.

The transcript must be editable before save. The dialog should never save raw transcript text without giving the user a chance to review it.

## Non-Goals

- No separate audio-only queue; voice transcripts save as normal terminal comments.
- No automatic terminal insertion after transcription.
- No auto-submit to the terminal.
- No required cloud dependency for existing typed-comment users.
- No provider-specific code in `terminal_annotator.core`.

## Package Layout

```text
terminal_annotator/
  core/
    transcription.py

  adapters/
    transcription/
      __init__.py
      litellm_provider.py

    terminator/
      dialog.py
      terminal_annotator_plugin.py
```

## Dependencies

Add an optional dependency group:

```toml
[project.optional-dependencies]
voice = ["litellm"]
```

Keep voice optional so current text-only users do not need LiteLLM or cloud credentials.

Recording should use available system tools at runtime:

1. `parecord`
2. `arecord`
3. `ffmpeg`

The implementation should detect available tools and show a readable error when none are installed.

## Configuration

Environment variables:

```text
TERMINAL_ANNOTATOR_TRANSCRIBE_PROVIDER=litellm
TERMINAL_ANNOTATOR_TRANSCRIBE_MODEL=openai/whisper-1
TERMINAL_ANNOTATOR_TRANSCRIBE_FALLBACKS=groq/whisper-large-v3,openai/whisper-1
```

Provider API keys should follow LiteLLM conventions, for example:

```text
OPENAI_API_KEY=...
GROQ_API_KEY=...
DEEPGRAM_API_KEY=...
MISTRAL_API_KEY=...
```

Optional LiteLLM proxy mode:

```text
TERMINAL_ANNOTATOR_LITELLM_BASE_URL=http://127.0.0.1:4000
TERMINAL_ANNOTATOR_LITELLM_API_KEY=<proxy-key>
```

## Core API

Add a terminal-agnostic transcription model:

```python
@dataclass(slots=True)
class TranscriptionResult:
    text: str
    provider: str
    model: str
    audio_path: str
    duration_seconds: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
```

Add config parsing:

```python
@dataclass(slots=True)
class TranscriptionConfig:
    provider: str
    model: str
    fallbacks: list[str]
    base_url: str | None = None
    api_key: str | None = None
```

The core can define these structures and environment parsing, but provider calls belong in adapter code.

## LiteLLM Provider

Implement:

```python
def transcribe_audio(audio_path: Path, config: TranscriptionConfig) -> TranscriptionResult:
    ...
```

Direct SDK mode:

- Import `litellm` lazily so text-only workflows do not require it.
- Call `litellm.transcription(...)`.
- Try `config.model` first, then configured fallback models in order.
- Return the first successful transcript.
- Raise a readable provider error if all attempts fail.

Proxy mode:

- Use `TERMINAL_ANNOTATOR_LITELLM_BASE_URL` and `TERMINAL_ANNOTATOR_LITELLM_API_KEY`.
- Keep the call path isolated so proxy behavior can be adjusted without changing GTK code.

## Audio Storage

Store recorded audio under runtime/cache storage:

```text
<storage-root>/audio/<temp-or-comment-id>.wav
```

After saving, add voice metadata to the comment:

```json
{
  "voice": {
    "audio_path": "/home/user/.cache/terminal-annotator/audio/abc123.wav",
    "provider": "litellm",
    "model": "openai/whisper-1",
    "transcribed_at": "2026-06-27T15:12:00+03:00"
  }
}
```

The formatter should continue using `comment`. It should not need special handling for voice-backed comments in the first implementation.

## GTK Dialog Changes

Add controls to the existing comment dialog:

- `Record`
- `Stop`
- status label for recording/transcribing/errors

Behavior:

- Save stays disabled while the comment text is empty.
- Recording and transcription must not block GTK.
- If transcription succeeds, insert the transcript into the comment buffer.
- If the user already typed text, append the transcript with a separating newline instead of replacing their text.
- If transcription fails, preserve existing typed text and show an error.

## CLI Support

Add debug commands:

```bash
terminal-ann transcribe <audio-path> [--model <model>]
terminal-ann add --session demo --text "selected output" --comment "..." --audio-path note.wav
```

The `transcribe` command is useful for verifying credentials and model support outside Terminator.

## Cleanup

Extend cleanup to remove audio files referenced only by deleted old sessions.

Rules:

- Missing referenced audio files should not fail cleanup.
- Malformed session files should not fail cleanup.
- Orphan audio cleanup can be a later enhancement if reference tracking becomes expensive.

## Tests

Automated:

- Config parsing from environment.
- Fallback model ordering.
- Missing optional LiteLLM dependency error.
- Successful mocked `litellm.transcription(...)`.
- Failed primary model with successful fallback.
- Metadata serialization.
- CLI `transcribe` argument handling.
- Cleanup behavior for referenced, missing, and stale audio files.

Manual:

- Short voice note.
- Long voice note.
- Cancel during recording.
- Transcription failure with typed text already present.
- Retry with fallback model.
- Transcript appears in the comment text box before save.
- Saved voice comments insert into terminal input like normal typed comments.

## Open Questions

- Should recorded audio be kept by default, or deleted after successful transcription?
- Should the UI expose model choice, or keep it environment-only for v1?
- Should LiteLLM proxy mode be documented as recommended for team use?
