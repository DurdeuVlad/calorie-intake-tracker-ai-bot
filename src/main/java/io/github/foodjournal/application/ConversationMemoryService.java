package io.github.foodjournal.application;

import io.github.foodjournal.domain.*;
import io.github.foodjournal.repository.*;
import java.util.*;
import org.springframework.stereotype.Service;

@Service
public class ConversationMemoryService {
 private static final int MAX_MESSAGES=10;
 private final ConversationMemoryRepository memory; private final FoodUserRepository users;
 public ConversationMemoryService(ConversationMemoryRepository memory,FoodUserRepository users){this.memory=memory;this.users=users;}
 public List<ConversationMemory> recent(FoodUser user){List<ConversationMemory> rows=new ArrayList<>(memory.findTop10ByUserOrderByCreatedAtDescIdDesc(user));Collections.reverse(rows);return List.copyOf(rows);}
 public void recordTurn(FoodUser user,String userMessage,String assistantMessage){FoodUser locked=users.lockById(user.getId()).orElseThrow();memory.save(new ConversationMemory(locked,"user",truncate(userMessage)));memory.save(new ConversationMemory(locked,"assistant",truncate(assistantMessage)));List<ConversationMemory> rows=memory.findByUserOrderByCreatedAtDescIdDesc(locked);if(rows.size()>MAX_MESSAGES)memory.deleteAll(rows.subList(MAX_MESSAGES,rows.size()));}
 private String truncate(String text){if(text==null)return "";return text.length()<=3500?text:text.substring(0,3500);}
}
