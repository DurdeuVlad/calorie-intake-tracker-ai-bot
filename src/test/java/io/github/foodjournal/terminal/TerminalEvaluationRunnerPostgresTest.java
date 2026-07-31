package io.github.foodjournal.terminal;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.when;

import io.github.foodjournal.application.JournalAgentModel;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

@SpringBootTest(properties={"food-journal.telegram-token=test","food-journal.webhook-secret=test","food-journal.allowed-telegram-user-ids=42","food-journal.terminal.user-id=42","food-journal.terminal.runner-enabled=false","food-journal.scheduling-enabled=false"})
@ActiveProfiles("terminal") @Testcontainers(disabledWithoutDocker=true)
class TerminalEvaluationRunnerPostgresTest {
  @Container static final PostgreSQLContainer<?> postgres=new PostgreSQLContainer<>("postgres:17-alpine");
  @DynamicPropertySource static void database(DynamicPropertyRegistry registry){registry.add("spring.datasource.url",postgres::getJdbcUrl);registry.add("spring.datasource.username",postgres::getUsername);registry.add("spring.datasource.password",postgres::getPassword);}
  @Autowired TerminalEvaluationRunner runner; @Autowired JdbcTemplate db; @MockitoBean JournalAgentModel model;

  @BeforeEach void modelRepliesWithoutTools(){when(model.next(org.mockito.ArgumentMatchers.any(),org.mockito.ArgumentMatchers.anyList(),org.mockito.ArgumentMatchers.anyList())).thenReturn(new JournalAgentModel.AgentReply("Hello",List.of()));}

  @Test void repeatsEachScenarioFromAResetTerminalUserState(@TempDir Path temp) throws Exception {
    Path fixture=temp.resolve("fixture.json"); Files.writeString(fixture, """
      {"version":"test","scenarios":[{"id":"isolated","turns":[
        {"input":"one","assertions":[{"category":"CONVERSATION","type":"entries_exact","value":0}]},
        {"input":"two","assertions":[{"category":"CONVERSATION","type":"entries_exact","value":0}]}
      ]}]}
      """);
    runner.run(fixture.toString());
    assertThat(db.queryForObject("select count(*) from food_users where telegram_user_id=42",Long.class)).isEqualTo(1L);
    assertThat(db.queryForObject("select count(*) from conversation_memory",Long.class)).isEqualTo(4L);
  }
}
