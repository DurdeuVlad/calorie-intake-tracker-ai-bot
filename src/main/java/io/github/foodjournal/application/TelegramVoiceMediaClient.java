package io.github.foodjournal.application;

public interface TelegramVoiceMediaClient {
  TransientVoicePayload download(String telegramFileId);
}
