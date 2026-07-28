package io.github.foodjournal.service;

import static org.mockito.Mockito.*;

import io.github.foodjournal.application.JournalApplicationService;
import io.github.foodjournal.config.BotProperties;
import io.github.foodjournal.repository.ProcessedTelegramUpdateRepository;
import io.github.foodjournal.repository.OutboundTelegramMessageRepository;
import io.github.foodjournal.telegram.*;
import java.util.Set;
import org.junit.jupiter.api.Test;

class UpdateServiceTest {
  @Test void ignoresDuplicateUpdateBeforeCallingApplicationService() {
    ProcessedTelegramUpdateRepository processed = mock(ProcessedTelegramUpdateRepository.class);
    OutboundTelegramMessageRepository outbound = mock(OutboundTelegramMessageRepository.class);
    JournalApplicationService journal = mock(JournalApplicationService.class);
    UpdateService service = new UpdateService(new BotProperties("token", "secret", Set.of(1L), "Europe/Bucharest", "", "test"), processed, outbound, journal, mock(io.github.foodjournal.application.VoiceTranscriber.class));
    TelegramUpdate update = new TelegramUpdate(77L, new TelegramMessage(5L, new TelegramChat(1L), new TelegramUser(1L, "A"), "I ate soup", null, null, null), null);
    when(processed.claimIfNew(77L)).thenReturn(0);

    service.handle(update);

    verify(processed).claimIfNew(77L);
    verifyNoInteractions(journal, outbound);
  }

  @Test void processesClaimedAllowedUpdateOnce() {
    ProcessedTelegramUpdateRepository processed = mock(ProcessedTelegramUpdateRepository.class);
    OutboundTelegramMessageRepository outbound = mock(OutboundTelegramMessageRepository.class);
    JournalApplicationService journal = mock(JournalApplicationService.class);
    UpdateService service = new UpdateService(new BotProperties("token", "secret", Set.of(1L), "Europe/Bucharest", "", "test"), processed, outbound, journal, mock(io.github.foodjournal.application.VoiceTranscriber.class));
    TelegramUpdate update = new TelegramUpdate(77L, new TelegramMessage(5L, new TelegramChat(1L), new TelegramUser(1L, "A"), "I ate soup", null, null, null), null);
    when(processed.claimIfNew(77L)).thenReturn(1);
    when(journal.handle(1L, 1L, "A", "I ate soup")).thenReturn("Logged");

    service.handle(update);

    verify(outbound).save(argThat(message -> message.getChatId() == 1L && message.getText().equals("Logged")));
  }

  @Test void ignoresNonAllowlistedUsersWithoutClaimingOrReplying() {
    ProcessedTelegramUpdateRepository processed = mock(ProcessedTelegramUpdateRepository.class);
    OutboundTelegramMessageRepository outbound = mock(OutboundTelegramMessageRepository.class);
    JournalApplicationService journal = mock(JournalApplicationService.class);
    UpdateService service = new UpdateService(new BotProperties("token", "secret", Set.of(1L), "Europe/Bucharest", "", "test"), processed, outbound, journal, mock(io.github.foodjournal.application.VoiceTranscriber.class));
    TelegramUpdate update = new TelegramUpdate(77L, new TelegramMessage(5L, new TelegramChat(2L), new TelegramUser(2L, "B"), "I ate soup", null, null, null), null);

    service.handle(update);

    verifyNoInteractions(processed, outbound, journal);
  }

  @Test void ignoresMalformedUpdatesWithoutClaimingOrReplying() {
    ProcessedTelegramUpdateRepository processed = mock(ProcessedTelegramUpdateRepository.class);
    OutboundTelegramMessageRepository outbound = mock(OutboundTelegramMessageRepository.class);
    JournalApplicationService journal = mock(JournalApplicationService.class);
    UpdateService service = new UpdateService(new BotProperties("token", "secret", Set.of(1L), "Europe/Bucharest", "", "test"), processed, outbound, journal, mock(io.github.foodjournal.application.VoiceTranscriber.class));

    service.handle(new TelegramUpdate(77L, null, null));

    verifyNoInteractions(processed, outbound, journal);
  }

  @Test void ignoresNullRootAndMissingChatIdWithoutSideEffects() {
    ProcessedTelegramUpdateRepository processed = mock(ProcessedTelegramUpdateRepository.class);
    OutboundTelegramMessageRepository outbound = mock(OutboundTelegramMessageRepository.class);
    JournalApplicationService journal = mock(JournalApplicationService.class);
    UpdateService service = new UpdateService(new BotProperties("token", "secret", Set.of(1L), "Europe/Bucharest", "", "test"), processed, outbound, journal, mock(io.github.foodjournal.application.VoiceTranscriber.class));

    service.handle(null);
    service.handle(new TelegramUpdate(77L, new TelegramMessage(5L, new TelegramChat(null), new TelegramUser(1L, "A"), "I ate soup", null, null, null), null));

    verifyNoInteractions(processed, outbound, journal);
  }

  @Test void routesVoiceTranscriptThroughTheJournalWithoutPersistingMedia() {
    ProcessedTelegramUpdateRepository processed = mock(ProcessedTelegramUpdateRepository.class); OutboundTelegramMessageRepository outbound = mock(OutboundTelegramMessageRepository.class); JournalApplicationService journal = mock(JournalApplicationService.class); io.github.foodjournal.application.VoiceTranscriber voice = mock(io.github.foodjournal.application.VoiceTranscriber.class);
    UpdateService service = new UpdateService(new BotProperties("token", "secret", Set.of(1L), "Europe/Bucharest", "", "test"), processed, outbound, journal, voice);
    when(processed.claimIfNew(77L)).thenReturn(1); when(voice.transcribe("voice-file","audio/ogg")).thenReturn("I ate soup"); when(journal.handle(1L,1L,"A","I ate soup")).thenReturn("Logged");
    service.handle(new TelegramUpdate(77L,new TelegramMessage(5L,new TelegramChat(1L),new TelegramUser(1L,"A"),null,new TelegramVoice("voice-file","audio/ogg",3),null,null),null));
    verify(voice).transcribe("voice-file","audio/ogg"); verify(journal).handle(1L,1L,"A","I ate soup");
  }

  @Test void transcriptionFailureDoesNotCallTheJournal() {
    ProcessedTelegramUpdateRepository processed = mock(ProcessedTelegramUpdateRepository.class); OutboundTelegramMessageRepository outbound = mock(OutboundTelegramMessageRepository.class); JournalApplicationService journal = mock(JournalApplicationService.class); io.github.foodjournal.application.VoiceTranscriber voice = mock(io.github.foodjournal.application.VoiceTranscriber.class);
    UpdateService service = new UpdateService(new BotProperties("token", "secret", Set.of(1L), "Europe/Bucharest", "", "test"), processed, outbound, journal, voice);
    when(processed.claimIfNew(77L)).thenReturn(1); when(voice.transcribe(anyString(),any())).thenThrow(new IllegalStateException());
    service.handle(new TelegramUpdate(77L,new TelegramMessage(5L,new TelegramChat(1L),new TelegramUser(1L,"A"),null,new TelegramVoice("voice-file","audio/ogg",3),null,null),null));
    verifyNoInteractions(journal); verify(outbound).save(argThat(message->message.getText().contains("could not transcribe")));
  }
}
