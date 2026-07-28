package io.github.foodjournal.service;

import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

import io.github.foodjournal.domain.*;
import io.github.foodjournal.repository.*;
import java.time.*;
import java.util.List;
import org.junit.jupiter.api.Test;

class ReportSchedulerTest {
 @Test void sendsAnOverdueMorningReportAfterRestartAndUsesTheDeliveryLedger(){UserSettingsRepository settings=mock(UserSettingsRepository.class);FoodEntryRepository entries=mock(FoodEntryRepository.class);ReportDeliveryRepository deliveries=mock(ReportDeliveryRepository.class);OutboundTelegramMessageRepository outbound=mock(OutboundTelegramMessageRepository.class);FoodUser user=new FoodUser(44L,"A");UserSettings profile=new UserSettings(user,"Europe/Bucharest");profile.completeOnboarding();when(settings.findAll()).thenReturn(List.of(profile));when(deliveries.claim(any(),eq("morning"),any())).thenReturn(1,0);when(entries.findByUserAndEatenAtBetweenOrderByEatenAtAsc(eq(user),any(),any())).thenReturn(List.of());ReportScheduler scheduler=new ReportScheduler(settings,entries,deliveries,outbound,Clock.fixed(Instant.parse("2026-07-28T05:05:00Z"),ZoneOffset.UTC));scheduler.deliverDueReports();scheduler.deliverDueReports();verify(outbound,times(1)).save(argThat(message->message.getChatId()==44L&&message.getText().contains("Good morning")));verify(deliveries,times(2)).claim(any(),eq("morning"),any());}
 @Test void doesNotSendBeforeAUsersLocalReportTime(){UserSettingsRepository settings=mock(UserSettingsRepository.class);FoodEntryRepository entries=mock(FoodEntryRepository.class);ReportDeliveryRepository deliveries=mock(ReportDeliveryRepository.class);OutboundTelegramMessageRepository outbound=mock(OutboundTelegramMessageRepository.class);FoodUser user=new FoodUser(44L,"A");UserSettings profile=new UserSettings(user,"Europe/Bucharest");profile.completeOnboarding();when(settings.findAll()).thenReturn(List.of(profile));new ReportScheduler(settings,entries,deliveries,outbound,Clock.fixed(Instant.parse("2026-07-28T04:59:00Z"),ZoneOffset.UTC)).deliverDueReports();verifyNoInteractions(deliveries,outbound,entries);}
 @Test void skipsReportsForDisabledOrIncompleteUsers(){UserSettingsRepository settings=mock(UserSettingsRepository.class);FoodEntryRepository entries=mock(FoodEntryRepository.class);ReportDeliveryRepository deliveries=mock(ReportDeliveryRepository.class);OutboundTelegramMessageRepository outbound=mock(OutboundTelegramMessageRepository.class);UserSettings incomplete=new UserSettings(new FoodUser(1L,"A"),"Europe/Bucharest");when(settings.findAll()).thenReturn(List.of(incomplete));new ReportScheduler(settings,entries,deliveries,outbound,Clock.fixed(Instant.parse("2026-07-28T21:30:00Z"),ZoneOffset.UTC)).deliverDueReports();verifyNoInteractions(deliveries,outbound,entries);}
}
