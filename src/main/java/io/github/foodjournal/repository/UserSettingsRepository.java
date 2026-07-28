package io.github.foodjournal.repository;
import io.github.foodjournal.domain.UserSettings; import org.springframework.data.jpa.repository.JpaRepository;
public interface UserSettingsRepository extends JpaRepository<UserSettings,Long>{}
