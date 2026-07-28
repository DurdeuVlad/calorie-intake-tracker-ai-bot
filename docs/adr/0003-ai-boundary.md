# ADR 0003: AI is an interpreter, not an authority

**Status:** Accepted

Gemini handles transcription and structured media extraction; OpenAI interprets natural language and drafts replies. Both adapters return typed, schema-validated data. Application services validate all fields and execute mutations deterministically. Original media is transient and never persisted.
