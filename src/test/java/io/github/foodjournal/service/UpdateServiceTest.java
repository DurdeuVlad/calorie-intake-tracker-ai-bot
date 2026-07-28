package io.github.foodjournal.service;

import static org.mockito.Mockito.*;

import io.github.foodjournal.application.JournalApplicationService;
import io.github.foodjournal.config.BotProperties;
import io.github.foodjournal.repository.ProcessedTelegramUpdateRepository;
import io.github.foodjournal.telegram.*;
import java.util.Set;
import org.junit.jupiter.api.Test;

class UpdateServiceTest {
  @Test void ignoresDuplicateUpdateBeforeCallingApplicationService() {
    ProcessedTelegramUpdateRepository processed = mock(ProcessedTelegramUpdateRepository.class);
    TelegramGateway telegram = mock(TelegramGateway.class);
    JournalApplicationService journal = mock(JournalApplicationService.class);
    UpdateService service = new UpdateService(new BotProperties("token", "secret", Set.of(1L), "Europe/Bucharest", "", "test"), processed, telegram, journal);
    TelegramUpdate update = new TelegramUpdate(77L, new TelegramMessage(5L, new TelegramChat(1L), new TelegramUser(1L, "A"), "I ate soup", null, null, null), null);
    when(processed.claimIfNew(77L)).thenReturn(0);

    service.handle(update);

    verify(processed).claimIfNew(77L);
    verifyNoInteractions(journal, telegram);
  }

  @Test void processesClaimedAllowedUpdateOnce() {
    ProcessedTelegramUpdateRepository processed = mock(ProcessedTelegramUpdateRepository.class);
    TelegramGateway telegram = mock(TelegramGateway.class);
    JournalApplicationService journal = mock(JournalApplicationService.class);
    UpdateService service = new UpdateService(new BotProperties("token", "secret", Set.of(1L), "Europe/Bucharest", "", "test"), processed, telegram, journal);
    TelegramUpdate update = new TelegramUpdate(77L, new TelegramMessage(5L, new TelegramChat(1L), new TelegramUser(1L, "A"), "I ate soup", null, null, null), null);
    when(processed.claimIfNew(77L)).thenReturn(1);
    when(journal.handle(1L, "A", "I ate soup")).thenReturn("Logged");

    service.handle(update);

    verify(telegram).sendMessage(1L, "Logged");
  }
}
