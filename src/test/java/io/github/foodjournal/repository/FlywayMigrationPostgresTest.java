package io.github.foodjournal.repository;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

@SpringBootTest(properties={"food-journal.telegram-token=test","food-journal.webhook-secret=test","food-journal.allowed-telegram-user-ids=1","food-journal.scheduling-enabled=false"})
@Testcontainers(disabledWithoutDocker=true)
class FlywayMigrationPostgresTest {
  @Container static final PostgreSQLContainer<?> POSTGRES = new PostgreSQLContainer<>("postgres:17-alpine");

  @DynamicPropertySource static void database(DynamicPropertyRegistry registry) {
    registry.add("spring.datasource.url", POSTGRES::getJdbcUrl);
    registry.add("spring.datasource.username", POSTGRES::getUsername);
    registry.add("spring.datasource.password", POSTGRES::getPassword);
  }

  @Autowired Flyway flyway;
  @Autowired JdbcTemplate jdbc;

  @Test void freshPostgresAppliesAllMigrationsAndPreservesJournalInvariants() {
    assertThat(flyway.info().current().getVersion().getVersion()).isEqualTo("8");
    List<String> tables = jdbc.queryForList("""
        select table_name from information_schema.tables
        where table_schema = 'public' and table_type = 'BASE TABLE'
        """, String.class);
    assertThat(tables).contains("food_users", "user_settings", "food_entries", "food_items",
        "processed_telegram_updates", "report_deliveries", "outbound_telegram_messages",
        "pinned_daily_status", "nutrition_source_cache", "private_foods", "pending_food_drafts", "pending_agent_actions", "conversation_memory",
        "flyway_schema_history");

    assertThat(hasUniqueConstraint("food_users", List.of("telegram_user_id"))).isTrue();
    assertThat(hasUniqueConstraint("report_deliveries", List.of("user_id", "report_type", "local_date"))).isTrue();
    assertThat(hasUniqueConstraint("private_foods", List.of("user_id", "name"))).isTrue();
    assertThat(hasUniqueConstraint("nutrition_source_cache", List.of("barcode"))).isTrue();

    assertThat(columnExists("food_items", "nutrition_source")).isTrue();
    assertThat(columnExists("food_items", "nutrition_confidence")).isTrue();
    assertThat(columnExists("pinned_daily_status", "lease_token")).isTrue();
  }

  private boolean hasUniqueConstraint(String table, List<String> columns) {
    Integer count = jdbc.queryForObject("""
        select count(*) from pg_constraint c
        join pg_class relation on relation.oid = c.conrelid
        where relation.relname = ? and c.contype = 'u'
          and (select string_agg(attribute.attname, ',' order by position.ordinality)
               from unnest(c.conkey) with ordinality as position(attribute_number, ordinality)
               join pg_attribute attribute on attribute.attrelid = relation.oid and attribute.attnum = position.attribute_number)
              = ?
        """, Integer.class, table, String.join(",", columns));
    return count != null && count > 0;
  }

  private boolean columnExists(String table, String column) {
    Integer count = jdbc.queryForObject("""
        select count(*) from information_schema.columns
        where table_schema = 'public' and table_name = ? and column_name = ?
        """, Integer.class, table, column);
    return count != null && count == 1;
  }
}
