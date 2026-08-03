package io.github.foodjournal.domain;

import jakarta.persistence.*;
import java.time.*;
import java.util.*;

/** One user-owned batch of journal mutations that can be reversed for ten minutes. */
@Entity @Table(name="journal_change_sets")
public class JournalChangeSet {
  public static final Duration UNDO_WINDOW=Duration.ofMinutes(10);
  @Id @GeneratedValue(strategy=GenerationType.IDENTITY) private Long id;
  @ManyToOne(optional=false) @JoinColumn(name="user_id") private FoodUser user;
  @Column(nullable=false) private Instant createdAt;
  @Column(nullable=false) private Instant expiresAt;
  private Instant undoneAt;
  @OneToMany(mappedBy="changeSet",cascade=CascadeType.ALL,orphanRemoval=true)
  @OrderBy("sequenceNumber asc") private List<JournalMutation> mutations=new ArrayList<>();

  protected JournalChangeSet(){}
  public static JournalChangeSet start(FoodUser user,Instant now){
    if(user==null||now==null)throw new IllegalArgumentException("User and start time are required");
    JournalChangeSet result=new JournalChangeSet();result.user=user;result.createdAt=now;result.expiresAt=now.plus(UNDO_WINDOW);return result;
  }
  public JournalMutation addMutation(JournalMutationType type,JournalEntrySnapshot before,JournalEntrySnapshot after){
    JournalMutation mutation=new JournalMutation(this,mutations.size(),type,before,after);mutations.add(mutation);return mutation;
  }
  public void markUndone(Instant now){if(now==null||!now.isBefore(expiresAt))throw new IllegalStateException("Change set is no longer undoable");if(undoneAt!=null)throw new IllegalStateException("Change set was already undone");undoneAt=now;}
  public Long getId(){return id;} public FoodUser getUser(){return user;} public Instant getCreatedAt(){return createdAt;} public Instant getExpiresAt(){return expiresAt;} public Instant getUndoneAt(){return undoneAt;}
  public List<JournalMutation> getMutations(){return Collections.unmodifiableList(mutations);} public boolean isUndoableAt(Instant now){return undoneAt==null&&now!=null&&now.isBefore(expiresAt);}
}
