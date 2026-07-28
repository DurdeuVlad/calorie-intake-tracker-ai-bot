package io.github.foodjournal.infrastructure.openfoodfacts;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.*;

import io.github.foodjournal.application.*;
import io.github.foodjournal.domain.*;
import io.github.foodjournal.repository.*;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.Optional;
import org.junit.jupiter.api.Test;

class CachedNutritionResolverTest {
 @Test void usesFreshCachedOpenFoodFactsValuesAndScalesToQuantity(){NutritionSourceCacheRepository cache=mock(NutritionSourceCacheRepository.class);PrivateFoodRepository privateFoods=mock(PrivateFoodRepository.class);OpenFoodFactsClient off=mock(OpenFoodFactsClient.class);when(cache.findByBarcode("3017624010701")).thenReturn(Optional.of(new NutritionSourceCache("3017624010701","Nutella",539,new BigDecimal("6.3"),new BigDecimal("57.5"),new BigDecimal("30.9"),"url",Instant.now())));var result=new CachedNutritionResolver(cache,privateFoods,off).resolve(new FoodUser(1,"A"),new JournalIntent.MealItem("Nutella",20d,null,null,null,null,"3017624010701"));assertThat(result.source()).isEqualTo("open_food_facts");assertThat(result.item().calories()).isEqualTo(108);verifyNoInteractions(off);}
 @Test void fallsBackToTheRequestingUsersPrivateFood(){NutritionSourceCacheRepository cache=mock(NutritionSourceCacheRepository.class);PrivateFoodRepository privateFoods=mock(PrivateFoodRepository.class);OpenFoodFactsClient off=mock(OpenFoodFactsClient.class);FoodUser user=new FoodUser(1,"A");when(privateFoods.findByUserAndNameIgnoreCase(user,"Grandma soup")).thenReturn(Optional.of(new PrivateFood(user,"Grandma soup",80,new BigDecimal("4"),new BigDecimal("10"),new BigDecimal("2"))));var result=new CachedNutritionResolver(cache,privateFoods,off).resolve(user,new JournalIntent.MealItem("Grandma soup",250d,null,null,null,null,null));assertThat(result.source()).isEqualTo("private_food");assertThat(result.item().calories()).isEqualTo(200);}
}
