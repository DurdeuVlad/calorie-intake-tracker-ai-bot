package io.github.foodjournal.repository;
import io.github.foodjournal.domain.ReportDelivery; import java.time.LocalDate; import org.springframework.data.jpa.repository.*; import org.springframework.data.repository.query.Param;
public interface ReportDeliveryRepository extends JpaRepository<ReportDelivery,Long>{
  @Modifying
  @Query(value="insert into report_deliveries (user_id, report_type, local_date, delivered_at) values (:userId, :reportType, :localDate, current_timestamp) on conflict (user_id, report_type, local_date) do nothing", nativeQuery=true)
  int claim(@Param("userId") Long userId, @Param("reportType") String reportType, @Param("localDate") LocalDate localDate);
}
