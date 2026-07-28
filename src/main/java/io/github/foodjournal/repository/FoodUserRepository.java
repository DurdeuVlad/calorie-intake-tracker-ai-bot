package io.github.foodjournal.repository;
import io.github.foodjournal.domain.FoodUser; import java.util.Optional; import org.springframework.data.jpa.repository.JpaRepository;
public interface FoodUserRepository extends JpaRepository<FoodUser,Long>{ Optional<FoodUser> findByTelegramUserId(long telegramUserId); }
