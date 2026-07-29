package io.github.foodjournal.application;

import io.github.foodjournal.domain.*;
import io.github.foodjournal.repository.ConversationMemoryRepository;
import java.util.*;
import org.springframework.stereotype.Service;

@Service
public class ConversationMemoryService {
 private static final int MAX_MESSAGES=10;
 private final ConversationMemoryRepository memory;
 public ConversationMemoryService(ConversationMemoryRepository memory){this.memory=memory;}
 public List<ConversationMemory> recent(FoodUser user){List<ConversationMemory> rows=new ArrayList<>(memory.findTop10ByUserOrderByCreatedAtDesc(user));Collections.reverse(rows);return List.copyOf(rows);}
 public void recordTurn(FoodUser user,String userMessage,String assistantMessage){memory.save(new ConversationMemory(user,"user",truncate(userMessage)));memory.save(new ConversationMemory(user,"assistant",truncate(assistantMessage)));List<ConversationMemory> rows=memory.findByUserOrderByCreatedAtDesc(user);if(rows.size()>MAX_MESSAGES)memory.deleteAll(rows.subList(MAX_MESSAGES,rows.size()));}
 private String truncate(String text){if(text==null)return "";return text.length()<=3500?text:text.substring(0,3500);}
}
