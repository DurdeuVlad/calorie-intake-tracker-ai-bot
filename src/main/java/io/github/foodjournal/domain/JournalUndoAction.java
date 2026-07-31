package io.github.foodjournal.domain;

import jakarta.persistence.*;
import java.time.*;

/** One short-lived, user-owned reversal point for a destructive journal action. */
@Entity @Table(name="journal_undo_actions")
public class JournalUndoAction {
  @Id private Long userId;
  @OneToOne @MapsId @JoinColumn(name="user_id") private FoodUser user;
  @Column(nullable=false) private Long entryId;
  @Column(nullable=false) private String actionType;
  @Column(nullable=false) private Instant expiresAt;
  protected JournalUndoAction() {}
  public static JournalUndoAction deletedEntry(FoodUser user, Long entryId, Instant now) {
    JournalUndoAction action=new JournalUndoAction(); action.user=user; action.entryId=entryId; action.actionType="DELETE";
    action.expiresAt=now.plus(Duration.ofMinutes(10)); return action;
  }
  public Long getEntryId(){return entryId;} public String getActionType(){return actionType;} public Instant getExpiresAt(){return expiresAt;}
}
