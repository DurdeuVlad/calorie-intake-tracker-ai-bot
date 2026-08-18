package io.github.foodjournal.terminal;

import static org.assertj.core.api.Assertions.assertThat;

import io.github.foodjournal.messaging.InboundMessage;
import io.github.foodjournal.messaging.MessagingDispatcher;
import io.github.foodjournal.messaging.MessagingIngressService;
import io.github.foodjournal.messaging.MessagingInboxWorker;
import java.time.Duration;
import java.util.List;
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
  @Autowired MessagingIngressService ingress; @Autowired MessagingInboxWorker inbox; @Autowired MessagingDispatcher outbox; @Autowired TerminalFrontend frontend;

  @Test void syntheticTerminalMessageTravelsThroughInboxWorkerAndOutbox() throws Exception {
    ingress.accept(new InboundMessage("terminal","9001","42","42","Local",null,"/start",null,List.of()));

    inbox.dispatch(); outbox.dispatch();

    String reply=frontend.awaitReply(Duration.ofSeconds(1));
    assertThat(reply).isNotNull();
    assertThat(reply).contains("IANA");
  }
}
