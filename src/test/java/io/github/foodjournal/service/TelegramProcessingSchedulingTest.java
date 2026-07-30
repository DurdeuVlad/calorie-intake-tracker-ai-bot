package io.github.foodjournal.service;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;

class TelegramProcessingSchedulingTest {
  @Test void workersAreNotConditionedOnOptionalReportScheduling(){assertThat(TelegramInboxWorker.class.isAnnotationPresent(ConditionalOnProperty.class)).isFalse();assertThat(OutboundTelegramDispatcher.class.isAnnotationPresent(ConditionalOnProperty.class)).isFalse();}
}
