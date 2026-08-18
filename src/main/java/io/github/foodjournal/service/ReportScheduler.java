package io.github.foodjournal.service;

import io.github.foodjournal.domain.*;
import io.github.foodjournal.repository.*;
import java.time.*;
import java.util.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@ConditionalOnProperty(prefix = "food-journal", name = "scheduling-enabled", havingValue = "true", matchIfMissing = true)
public class ReportScheduler {
  private final UserSettingsRepository settings;
  private final FoodEntryRepository entries;
  private final ReportDeliveryRepository deliveries;
  private final MessagingRouteRepository routes;
  private final MessagingOutboundRepository outbound;
  private final Clock clock;

  @Autowired
  public ReportScheduler(
      UserSettingsRepository s,
      FoodEntryRepository e,
      ReportDeliveryRepository d,
      MessagingRouteRepository routes,
      MessagingOutboundRepository outbound) {
    this(s, e, d, routes, outbound, Clock.systemUTC());
  }

  ReportScheduler(
      UserSettingsRepository s,
      FoodEntryRepository e,
      ReportDeliveryRepository d,
      MessagingRouteRepository routes,
      MessagingOutboundRepository outbound,
      Clock c) {
    this.settings = s;
    this.entries = e;
    this.deliveries = d;
    this.routes = routes;
    this.outbound = outbound;
    this.clock = c;
  }

  @Scheduled(cron = "0 * * * * *")
  @Transactional
  public void deliverDueReports() {
    for (UserSettings s : settings.findAll()) {
      if (!s.isOnboardingCompleted() || !s.isReportsEnabled()) continue;
      ZoneId z;
      try {
        z = ZoneId.of(s.getTimezone());
      } catch (Exception x) {
        continue;
      }
      ZonedDateTime now = Instant.now(clock).atZone(z);
      if (!now.toLocalTime().isBefore(s.getMorningReportTime())) send(s, "morning", now.toLocalDate());
      if (!now.toLocalTime().isBefore(s.getEveningReportTime())) send(s, "evening", now.toLocalDate());
      if (now.toLocalTime().isBefore(LocalTime.of(2, 0))) {
        LocalDate previous = now.toLocalDate().minusDays(1);
        send(s, "morning", previous);
        send(s, "evening", previous);
      }
    }
  }

  private void send(UserSettings s, String type, LocalDate date) {
    if (deliveries.claim(s.getUser().getId(), type, date) == 0) return;
    ZoneId z = ZoneId.of(s.getTimezone());
    List<FoodEntry> day = entries.findByUserAndEatenAtBetweenOrderByEatenAtAsc(
        s.getUser(), date.atStartOfDay(z).toInstant(), date.plusDays(1).atStartOfDay(z).toInstant());
    int calories = day.stream().map(FoodEntry::getCalories).filter(Objects::nonNull).mapToInt(Integer::intValue).sum();
    String text = (type.equals("morning") ? "Good morning. " : "Daily summary: ") + day.size() + " meals, " + calories + " kcal logged.";
    for (MessagingRoute route : routes.findByUser(s.getUser())) {
      outbound.save(new MessagingOutboundMessage(route.getProvider(), route.getConversationId(), text));
    }
  }
}
