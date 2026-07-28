package io.github.foodjournal.repository;

import static org.assertj.core.api.Assertions.assertThat;

import io.github.foodjournal.domain.OutboundTelegramMessage;
import io.github.foodjournal.service.OutboundTelegramClaimService;
import java.util.concurrent.*;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

@SpringBootTest(properties={"food-journal.telegram-token=test","food-journal.webhook-secret=test","food-journal.allowed-telegram-user-ids=1","food-journal.scheduling-enabled=false"})
@Testcontainers(disabledWithoutDocker=true)
class OutboundTelegramClaimPostgresTest {
  @Container static final PostgreSQLContainer<?> POSTGRES = new PostgreSQLContainer<>("postgres:17-alpine");
  @DynamicPropertySource static void database(DynamicPropertyRegistry registry) {
    registry.add("spring.datasource.url", POSTGRES::getJdbcUrl);
    registry.add("spring.datasource.username", POSTGRES::getUsername);
    registry.add("spring.datasource.password", POSTGRES::getPassword);
  }
  @Autowired OutboundTelegramMessageRepository messages;
  @Autowired OutboundTelegramClaimService claims;

  @Test void concurrentClaimersReceiveEachPendingMessageOnlyOnce() throws Exception {
    messages.saveAndFlush(new OutboundTelegramMessage(1L, "one"));
    ExecutorService pool = Executors.newFixedThreadPool(2);
    CountDownLatch start = new CountDownLatch(1);
    Future<Integer> first = pool.submit(() -> { start.await(); return claims.claimBatch().size(); });
    Future<Integer> second = pool.submit(() -> { start.await(); return claims.claimBatch().size(); });
    start.countDown();
    assertThat(first.get(10, TimeUnit.SECONDS) + second.get(10, TimeUnit.SECONDS)).isEqualTo(1);
    pool.shutdownNow();
  }
}
