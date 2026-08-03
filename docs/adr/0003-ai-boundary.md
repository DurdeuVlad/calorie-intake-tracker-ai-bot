# ADR 0003: AI is an interpreter, not an authority

**Status:** Accepted

OpenAI handles transcription, structured media extraction, natural-language interpretation, and replies. Adapters return typed, schema-validated data. Application services validate all fields and execute mutations deterministically. Original media is transient and never persisted.
