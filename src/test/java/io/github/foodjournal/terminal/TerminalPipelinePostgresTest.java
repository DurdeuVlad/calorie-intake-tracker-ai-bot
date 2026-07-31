package io.github.foodjournal.terminal;

import static org.assertj.core.api.Assertions.assertThat;

import io.github.foodjournal.service.*;
import io.github.foodjournal.telegram.*;
import java.time.Duration;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

@SpringBootTest(properties={"food-journal.telegram-token=test","food-journal.webhook-secret=test","food-journal.allowed-telegram-user-ids=42","food-journal.terminal.user-id=42","food-journal.terminal.runner-enabled=false","spring.task.scheduling.enabled=false"})
@ActiveProfiles("terminal") @Testcontainers(disabledWithoutDocker=true)
class TerminalPipelinePostgresTest {
  @Container static final PostgreSQLContainer<?> postgres=new PostgreSQLContainer<>("postgres:17-alpine");
  @DynamicPropertySource static void database(DynamicPropertyRegistry registry) { registry.add("spring.datasource.url",postgres::getJdbcUrl); registry.add("spring.datasource.username",postgres::getUsername); registry.add("spring.datasource.password",postgres::getPassword); }
  @Autowired UpdateService updates; @Autowired TelegramInboxWorker inbox; @Autowired OutboundTelegramDispatcher outbox; @Autowired TerminalTelegramGateway terminal;

  @Test void syntheticTerminalUpdateTravelsThroughInboxWorkerAndOutbox() throws Exception {
    long updateId=9001L;
    updates.enqueue(new TelegramUpdate(updateId,new TelegramMessage(updateId,new TelegramChat(42L),new TelegramUser(42L,"Local"),"/start",null,null,null),null));

    inbox.dispatch(); outbox.dispatch();

    TerminalTelegramGateway.Delivery reply=terminal.await(updateId,Duration.ofSeconds(1));
    assertThat(reply).isNotNull();
    assertThat(reply.text()).contains("IANA");
  }
}
