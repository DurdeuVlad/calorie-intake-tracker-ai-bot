package io.github.foodjournal.repository;
import io.github.foodjournal.domain.MessagingIdentity; import java.util.*; import org.springframework.data.jpa.repository.JpaRepository;
public interface MessagingIdentityRepository extends JpaRepository<MessagingIdentity,Long>{ Optional<MessagingIdentity> findByProviderAndExternalUserId(String provider,String externalUserId); }
