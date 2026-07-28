package io.github.foodjournal.domain;

import jakarta.persistence.*;
import java.time.LocalTime;

@Entity @Table(name="user_settings")
public class UserSettings {
  @Id private Long userId;
  @OneToOne @MapsId @JoinColumn(name="user_id") private FoodUser user;
  @Column(nullable=false) private String timezone;
  private Integer calorieTarget;
  @Column(nullable=false) private boolean reportsEnabled=true;
  @Column(nullable=false) private LocalTime morningReportTime=LocalTime.of(8,0);
  @Column(nullable=false) private LocalTime eveningReportTime=LocalTime.of(22,0);
  private Long pinnedMessageId;
  @Column(nullable=false) private boolean onboardingCompleted=false;
  @Column(nullable=false) private String onboardingStage="TIMEZONE";
  protected UserSettings() {}
  public UserSettings(FoodUser user, String timezone) { this.user=user; this.timezone=timezone; }
  public String getTimezone(){return timezone;} public Integer getCalorieTarget(){return calorieTarget;}
  public FoodUser getUser(){return user;} public boolean isReportsEnabled(){return reportsEnabled;} public LocalTime getMorningReportTime(){return morningReportTime;} public LocalTime getEveningReportTime(){return eveningReportTime;}
  public void setTimezone(String timezone){this.timezone=timezone;} public void setCalorieTarget(Integer target){this.calorieTarget=target;} public void setReportsEnabled(boolean enabled){this.reportsEnabled=enabled;}
  public Long getPinnedMessageId(){return pinnedMessageId;} public void setPinnedMessageId(Long value){pinnedMessageId=value;}
  public boolean isOnboardingCompleted(){return onboardingCompleted;} public void completeOnboarding(){onboardingCompleted=true;}
  public String getOnboardingStage(){return onboardingStage;} public void requireCalorieTarget(){onboardingStage="CALORIE_TARGET";} public void skipCalorieTarget(){onboardingStage="COMPLETE";onboardingCompleted=true;}
}
