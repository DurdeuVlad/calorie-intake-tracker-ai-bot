package io.github.foodjournal.infrastructure.openfoodfacts;

import io.github.foodjournal.application.*;
import io.github.foodjournal.domain.*;
import io.github.foodjournal.repository.*;
import java.math.BigDecimal;
import java.time.*;
import org.springframework.stereotype.Component;

@Component public class CachedNutritionResolver implements NutritionResolver {
 private final NutritionSourceCacheRepository cache; private final PrivateFoodRepository privateFoods; private final OpenFoodFactsClient off;
 public CachedNutritionResolver(NutritionSourceCacheRepository c,PrivateFoodRepository p,OpenFoodFactsClient o){cache=c;privateFoods=p;off=o;}
 public ResolvedMealItem resolve(FoodUser user,JournalIntent.MealItem item){if(item==null||item.grams()==null||item.grams()<=0)return new ResolvedMealItem(item,"manual");if(item.caloriesPer100g()!=null)return new ResolvedMealItem(new JournalIntent.MealItem(item.name(),item.grams(),value(item.caloriesPer100g(),item.grams()/100d),item.caloriesPer100g(),item.proteinGrams(),item.carbsGrams(),item.fatGrams(),item.barcode()),"manual");if(item.barcode()!=null){NutritionSourceCache existing=cache.findByBarcode(item.barcode()).orElse(null);NutritionProfile profile=existing!=null&&existing.getFetchedAt().isAfter(Instant.now().minus(Duration.ofDays(30)))?profile(existing):off.byBarcode(item.barcode()).map(p->{if(existing==null)cache.save(new NutritionSourceCache(item.barcode(),p.name(),p.caloriesPer100g(),decimal(p.proteinPer100g()),decimal(p.carbsPer100g()),decimal(p.fatPer100g()),p.sourceUrl(),Instant.now()));else existing.refresh(p.name(),p.caloriesPer100g(),decimal(p.proteinPer100g()),decimal(p.carbsPer100g()),decimal(p.fatPer100g()),p.sourceUrl(),Instant.now());return p;}).orElse(null);if(profile!=null)return new ResolvedMealItem(scale(item,profile),"open_food_facts");}return privateFoods.findByUserAndNameIgnoreCase(user,item.name()).map(p->new ResolvedMealItem(scale(item,profile(p)),"private_food")).orElse(new ResolvedMealItem(item,"manual"));}
 private NutritionProfile profile(NutritionSourceCache c){return new NutritionProfile(c.getProductName(),c.getCaloriesPer100g(),doubleValue(c.getProteinPer100g()),doubleValue(c.getCarbsPer100g()),doubleValue(c.getFatPer100g()),"open_food_facts",c.getSourceUrl());}
 private NutritionProfile profile(PrivateFood p){return new NutritionProfile(p.getName(),p.getCaloriesPer100g(),doubleValue(p.getProteinPer100g()),doubleValue(p.getCarbsPer100g()),doubleValue(p.getFatPer100g()),"private_food",null);}
 private JournalIntent.MealItem scale(JournalIntent.MealItem item,NutritionProfile p){double factor=item.grams()/100d;return new JournalIntent.MealItem(p.name(),item.grams(),value(p.caloriesPer100g(),factor),p.caloriesPer100g(),value(p.proteinPer100g(),factor),value(p.carbsPer100g(),factor),value(p.fatPer100g(),factor),item.barcode());}
 private Integer value(Integer value,double factor){return value==null?null:(int)Math.round(value*factor);} private Double value(Double value,double factor){return value==null?null:value*factor;} private BigDecimal decimal(Double value){return value==null?null:BigDecimal.valueOf(value);} private Double doubleValue(BigDecimal value){return value==null?null:value.doubleValue();}
}
