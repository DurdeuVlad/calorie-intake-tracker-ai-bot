package io.github.foodjournal.infrastructure.openfoodfacts;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.client.ExpectedCount.once;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

class OpenFoodFactsClientTest {
 @Test void readsNutritionPer100gFromTheBarcodeEndpoint() {
  RestClient.Builder builder=RestClient.builder().baseUrl("https://world.openfoodfacts.org/api/v2"); MockRestServiceServer server=MockRestServiceServer.bindTo(builder).build();
  server.expect(once(),requestTo("https://world.openfoodfacts.org/api/v2/product/3017624010701?fields=code,product_name,nutriments")).andRespond(withSuccess("{\"status\":1,\"product\":{\"product_name\":\"Nutella\",\"nutriments\":{\"energy-kcal_100g\":539,\"proteins_100g\":6.3,\"carbohydrates_100g\":57.5,\"fat_100g\":30.9}}}",MediaType.APPLICATION_JSON));
  var profile=new OpenFoodFactsClient(builder.build()).byBarcode("3017624010701");
  assertThat(profile).isPresent();assertThat(profile.get().caloriesPer100g()).isEqualTo(539);assertThat(profile.get().carbsPer100g()).isEqualTo(57.5);server.verify();
 }
 @Test void rejectsInvalidBarcodesWithoutNetworkAccess(){assertThat(new OpenFoodFactsClient(RestClient.create()).byBarcode("not-a-barcode")).isEmpty();}
}
