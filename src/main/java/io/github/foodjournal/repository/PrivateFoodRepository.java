package io.github.foodjournal.repository;
import io.github.foodjournal.domain.*; import java.util.Optional; import org.springframework.data.jpa.repository.JpaRepository;
public interface PrivateFoodRepository extends JpaRepository<PrivateFood,Long>{ Optional<PrivateFood> findByUserAndNameIgnoreCase(FoodUser user,String name); }
