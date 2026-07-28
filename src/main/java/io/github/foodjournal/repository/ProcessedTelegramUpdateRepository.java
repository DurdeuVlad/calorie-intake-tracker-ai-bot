package io.github.foodjournal.repository;
import io.github.foodjournal.domain.ProcessedTelegramUpdate; import org.springframework.data.jpa.repository.JpaRepository;
public interface ProcessedTelegramUpdateRepository extends JpaRepository<ProcessedTelegramUpdate,Long>{}
