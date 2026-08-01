package io.github.foodjournal.repository;
import io.github.foodjournal.domain.*; import java.util.*; import org.springframework.data.jpa.repository.JpaRepository;
public interface MessagingRouteRepository extends JpaRepository<MessagingRoute,Long>{ Optional<MessagingRoute> findByUserAndProviderAndConversationId(FoodUser user,String provider,String conversationId); List<MessagingRoute> findByUser(FoodUser user); }
