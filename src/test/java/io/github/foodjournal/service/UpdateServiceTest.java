package io.github.foodjournal.service;

import static org.mockito.Mockito.*;

import io.github.foodjournal.application.JournalApplicationService;
import io.github.foodjournal.config.BotProperties;
import io.github.foodjournal.repository.ProcessedTelegramUpdateRepository;
import io.github.foodjournal.repository.OutboundTelegramMessageRepository;
import io.github.foodjournal.repository.TelegramInboxUpdateRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.github.foodjournal.telegram.*;
import java.util.Set;
import org.junit.jupiter.api.Test;

class UpdateServiceTest {
  @Test void enqueuesClaimedUpdateWithoutCallingTheAgent() {
    ProcessedTelegramUpdateRepository processed=mock(ProcessedTelegramUpdateRepository.class); TelegramInboxUpdateRepository inbox=mock(TelegramInboxUpdateRepository.class); JournalApplicationService journal=mock(JournalApplicationService.class);
    UpdateService service=new UpdateService(new BotProperties("token","secret",Set.of(1L),"Europe/Bucharest","","test"),processed,mock(OutboundTelegramMessageRepository.class),journal,mock(io.github.foodjournal.application.VoiceTranscriber.class),(file,mime,type)->"",null,null,inbox,new ObjectMapper());
    TelegramUpdate update=new TelegramUpdate(90L,new TelegramMessage(1L,new TelegramChat(1L),new TelegramUser(1L,"A"),"hello",null,null,null),null); when(processed.claimIfNew(90L)).thenReturn(1);
    service.enqueue(update);
    verify(inbox).save(argThat(row->row.getUpdateId()==90L&&row.getTelegramUserId()==1L)); verifyNoInteractions(journal);
  }
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

  @Test void routesLargestPhotoExtractionThroughTheJournalWithoutPersistingMedia() {
    ProcessedTelegramUpdateRepository processed = mock(ProcessedTelegramUpdateRepository.class); OutboundTelegramMessageRepository outbound = mock(OutboundTelegramMessageRepository.class); JournalApplicationService journal = mock(JournalApplicationService.class); io.github.foodjournal.application.FoodMediaExtractor media = mock(io.github.foodjournal.application.FoodMediaExtractor.class);
    UpdateService service = new UpdateService(new BotProperties("token", "secret", Set.of(1L), "Europe/Bucharest", "", "test"), processed, outbound, journal, mock(io.github.foodjournal.application.VoiceTranscriber.class), media);
    when(processed.claimIfNew(78L)).thenReturn(1); when(media.extract("large","image/jpeg",io.github.foodjournal.application.FoodMediaType.PHOTO)).thenReturn("two eggs"); when(journal.handleMediaEvidence(1L,1L,"A","two eggs\nUser caption: breakfast")).thenReturn("Logged");
    service.handle(new TelegramUpdate(78L,new TelegramMessage(5L,new TelegramChat(1L),new TelegramUser(1L,"A"),null,null,java.util.List.of(new TelegramPhoto("small",10,10,10),new TelegramPhoto("large",20,20,20)),null,"breakfast"),null));
    verify(media).extract("large","image/jpeg",io.github.foodjournal.application.FoodMediaType.PHOTO); verify(journal).handleMediaEvidence(1L,1L,"A","two eggs\nUser caption: breakfast");
  }

  @Test void documentExtractionFailureDoesNotCallTheJournal() {
    ProcessedTelegramUpdateRepository processed = mock(ProcessedTelegramUpdateRepository.class); OutboundTelegramMessageRepository outbound = mock(OutboundTelegramMessageRepository.class); JournalApplicationService journal = mock(JournalApplicationService.class); io.github.foodjournal.application.FoodMediaExtractor media = mock(io.github.foodjournal.application.FoodMediaExtractor.class);
    UpdateService service = new UpdateService(new BotProperties("token", "secret", Set.of(1L), "Europe/Bucharest", "", "test"), processed, outbound, journal, mock(io.github.foodjournal.application.VoiceTranscriber.class), media);
    when(processed.claimIfNew(79L)).thenReturn(1); when(media.extract("file","text/plain",io.github.foodjournal.application.FoodMediaType.DOCUMENT)).thenThrow(new IllegalArgumentException());
    service.handle(new TelegramUpdate(79L,new TelegramMessage(5L,new TelegramChat(1L),new TelegramUser(1L,"A"),null,null,null,new TelegramDocument("file","label.txt","text/plain",3)),null));
    verifyNoInteractions(journal); verify(outbound).save(argThat(message->message.getText().contains("could not analyze that document")));
  }

  @Test void routesPdfEvidenceToTheAiEstimateJournalBoundary() {
    ProcessedTelegramUpdateRepository processed = mock(ProcessedTelegramUpdateRepository.class); OutboundTelegramMessageRepository outbound = mock(OutboundTelegramMessageRepository.class); JournalApplicationService journal = mock(JournalApplicationService.class); io.github.foodjournal.application.FoodMediaExtractor media = mock(io.github.foodjournal.application.FoodMediaExtractor.class);
    UpdateService service = new UpdateService(new BotProperties("token", "secret", Set.of(1L), "Europe/Bucharest", "", "test"), processed, outbound, journal, mock(io.github.foodjournal.application.VoiceTranscriber.class), media);
    when(processed.claimIfNew(80L)).thenReturn(1); when(media.extract("pdf","application/pdf",io.github.foodjournal.application.FoodMediaType.DOCUMENT)).thenReturn("Cereal, 120 kcal"); when(journal.handleMediaEvidence(1L,1L,"A","Cereal, 120 kcal")).thenReturn("Logged: Cereal. Nutrition values from media are estimates.");
    service.handle(new TelegramUpdate(80L,new TelegramMessage(5L,new TelegramChat(1L),new TelegramUser(1L,"A"),null,null,null,new TelegramDocument("pdf","label.pdf","application/pdf",100)),null));
    verify(media).extract("pdf","application/pdf",io.github.foodjournal.application.FoodMediaType.DOCUMENT); verify(journal).handleMediaEvidence(1L,1L,"A","Cereal, 120 kcal"); verify(outbound).save(argThat(message->message.getText().contains("estimates")));
  }
}
