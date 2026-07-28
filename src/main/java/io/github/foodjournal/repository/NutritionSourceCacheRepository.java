package io.github.foodjournal.repository;
import io.github.foodjournal.domain.NutritionSourceCache; import java.util.Optional; import org.springframework.data.jpa.repository.JpaRepository;
public interface NutritionSourceCacheRepository extends JpaRepository<NutritionSourceCache,Long>{ Optional<NutritionSourceCache> findByBarcode(String barcode); }
