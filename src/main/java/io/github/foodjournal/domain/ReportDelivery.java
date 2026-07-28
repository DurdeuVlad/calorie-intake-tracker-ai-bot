package io.github.foodjournal.domain;
import jakarta.persistence.*;
import java.time.*;
@Entity @Table(name="report_deliveries", uniqueConstraints=@UniqueConstraint(columnNames={"user_id","report_type","local_date"}))
public class ReportDelivery { @Id @GeneratedValue(strategy=GenerationType.IDENTITY) private Long id; @ManyToOne(optional=false) @JoinColumn(name="user_id") private FoodUser user; @Column(nullable=false) private String reportType; @Column(nullable=false) private LocalDate localDate; @Column(nullable=false) private Instant deliveredAt=Instant.now(); protected ReportDelivery(){} public ReportDelivery(FoodUser user,String type,LocalDate date){this.user=user;this.reportType=type;this.localDate=date;} }
