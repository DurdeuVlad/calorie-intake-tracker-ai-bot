package io.github.foodjournal.domain;

import jakarta.persistence.*;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

@Entity @Table(name="journal_change_mutations",uniqueConstraints=@UniqueConstraint(columnNames={"change_set_id","sequence_number"}))
public class JournalMutation {
  @Id @GeneratedValue(strategy=GenerationType.IDENTITY) private Long id;
  @ManyToOne(optional=false,fetch=FetchType.LAZY) @JoinColumn(name="change_set_id") private JournalChangeSet changeSet;
  @Column(nullable=false) private int sequenceNumber;
  @Enumerated(EnumType.STRING) @Column(nullable=false,length=16) private JournalMutationType actionType;
  @JdbcTypeCode(SqlTypes.JSON) @Column(columnDefinition="jsonb") private JournalEntrySnapshot beforeState;
  @JdbcTypeCode(SqlTypes.JSON) @Column(columnDefinition="jsonb") private JournalEntrySnapshot afterState;

  protected JournalMutation(){}
  JournalMutation(JournalChangeSet changeSet,int sequenceNumber,JournalMutationType actionType,JournalEntrySnapshot beforeState,JournalEntrySnapshot afterState){
    if(changeSet==null||actionType==null)throw new IllegalArgumentException("Change set and action type are required");
    if(actionType==JournalMutationType.CREATE&&afterState==null)throw new IllegalArgumentException("CREATE requires after state");
    if(actionType!=JournalMutationType.CREATE&&beforeState==null)throw new IllegalArgumentException(actionType+" requires before state");
    this.changeSet=changeSet;this.sequenceNumber=sequenceNumber;this.actionType=actionType;this.beforeState=beforeState;this.afterState=afterState;
  }
  public Long getId(){return id;} public int getSequenceNumber(){return sequenceNumber;} public JournalMutationType getActionType(){return actionType;}
  public JournalEntrySnapshot getBeforeState(){return beforeState;} public JournalEntrySnapshot getAfterState(){return afterState;}
}
