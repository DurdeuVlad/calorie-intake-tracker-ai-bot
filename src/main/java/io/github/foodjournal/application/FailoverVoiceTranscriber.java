package io.github.foodjournal.application;

import io.micrometer.core.instrument.MeterRegistry;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

/** Downloads voice once, then uses OpenAI only when Gemini fails at a provider boundary. */
@Component
public class FailoverVoiceTranscriber implements VoiceTranscriber {
  private static final int MAX_VOICE_BYTES = 20_000_000;
  private static final Logger log = LoggerFactory.getLogger(FailoverVoiceTranscriber.class);
  private final TelegramVoiceMediaClient media;
  private final VoiceTranscriptionProvider gemini;
  private final VoiceTranscriptionProvider openai;
  private final MeterRegistry metrics;

  @Autowired public FailoverVoiceTranscriber(TelegramVoiceMediaClient media, io.github.foodjournal.infrastructure.gemini.GeminiVoiceTranscriber gemini, io.github.foodjournal.infrastructure.openai.OpenAiVoiceTranscriptionProvider openai, MeterRegistry metrics) {
    this.media = media; this.gemini = gemini; this.openai = openai; this.metrics = metrics;
  }
  FailoverVoiceTranscriber(TelegramVoiceMediaClient media, VoiceTranscriptionProvider gemini, VoiceTranscriptionProvider openai, MeterRegistry metrics) { this.media = media; this.gemini = gemini; this.openai = openai; this.metrics = metrics; }

  @Override public String transcribe(String telegramFileId, String mimeType) {
    try (TransientVoicePayload payload = media.download(telegramFileId)) {
      byte[] bytes = payload.bytes();
      if (bytes == null || bytes.length == 0 || bytes.length > MAX_VOICE_BYTES) throw failure(MediaProcessingException.Category.INVALID_MEDIA, "Voice note is invalid");
      try {
        String transcript = gemini.transcribe(bytes, mimeType);
        count("success", "gemini", null); return transcript;
      } catch (MediaProcessingException geminiFailure) {
        count("failure", "gemini", geminiFailure.category()); logFailure("gemini", geminiFailure);
        if (!fallbackEligible(geminiFailure)) throw geminiFailure;
        count("fallback", "gemini_to_openai", geminiFailure.category());
        try {
          String transcript = openai.transcribe(bytes, mimeType);
          count("success", "openai", null); return transcript;
        } catch (MediaProcessingException openaiFailure) {
          count("failure", "openai", openaiFailure.category()); logFailure("openai", openaiFailure);
          throw openaiFailure;
        }
      }
    } catch (MediaProcessingException failure) {
      if (failure.category() == MediaProcessingException.Category.TELEGRAM_DOWNLOAD || failure.category() == MediaProcessingException.Category.INVALID_MEDIA) count("failure", "telegram", failure.category());
      throw failure;
    } catch (RuntimeException failure) {
      count("failure", "telegram", MediaProcessingException.Category.TELEGRAM_DOWNLOAD);
      throw failure(MediaProcessingException.Category.TELEGRAM_DOWNLOAD, "Telegram media download failed", failure);
    }
  }

  static boolean fallbackEligible(MediaProcessingException failure) { return switch (failure.category()) { case NOT_CONFIGURED, MODEL_UNAVAILABLE, RATE_LIMITED, PROVIDER_TEMPORARY, PROVIDER_RESPONSE -> true; case TELEGRAM_DOWNLOAD, INVALID_MEDIA -> false; }; }
  private void logFailure(String provider, MediaProcessingException failure) { log.warn("voice_transcription_failure provider={} category={} status={}", provider, failure.category(), statusClass(failure)); }
  private String statusClass(MediaProcessingException failure) { Throwable cause = failure.getCause(); if (cause instanceof org.springframework.web.client.RestClientResponseException response) return response.getStatusCode().value() / 100 + "xx"; return "none"; }
  private void count(String result, String provider, MediaProcessingException.Category category) { metrics.counter("food_journal_voice_transcriptions_total", "result", result, "provider", provider, "category", category == null ? "none" : category.name()).increment(); }
  private MediaProcessingException failure(MediaProcessingException.Category category, String message) { return new MediaProcessingException(category, message); }
  private MediaProcessingException failure(MediaProcessingException.Category category, String message, Throwable cause) { return new MediaProcessingException(category, message, cause); }
}
