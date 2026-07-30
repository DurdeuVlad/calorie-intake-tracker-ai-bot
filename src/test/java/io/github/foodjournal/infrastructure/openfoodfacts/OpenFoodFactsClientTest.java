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
 @Test void searchesRanksAndCapsPackagedFoodResults() {
  RestClient.Builder builder=RestClient.builder().baseUrl("https://world.openfoodfacts.org/api/v2"); MockRestServiceServer server=MockRestServiceServer.bindTo(builder).build();
  server.expect(once(),requestTo("https://world.openfoodfacts.org/api/v2/search?search_terms=crenvusti&fields=code,product_name,brands,nutriments&page_size=20")).andRespond(withSuccess("""
   {"products":[
    {"code":"12345678","product_name":"Crenvusti","brands":"Prima","nutriments":{"energy-kcal_100g":250}},
    {"code":"12345679","product_name":"Crenvusti afumati","brands":"Alta","nutriments":{"energy-kcal_100g":260}},
    {"code":"12345670","product_name":"Crenvusti pui","brands":"Brand","nutriments":{"energy-kcal_100g":240}},
    {"code":"12345671","product_name":"Crenvusti vita","brands":"Brand","nutriments":{"energy-kcal_100g":230}},
    {"code":"12345672","product_name":"Crenvusti porc","brands":"Brand","nutriments":{"energy-kcal_100g":220}},
    {"code":"12345673","product_name":"Crenvusti extra","brands":"Brand","nutriments":{"energy-kcal_100g":210}},
    {"code":"invalid","product_name":"Bad barcode","brands":"Brand","nutriments":{"energy-kcal_100g":200}},
    {"code":"12345674","product_name":"No calories","brands":"Brand","nutriments":{}}
   ]}""",MediaType.APPLICATION_JSON));
  var results=new OpenFoodFactsClient(builder.build()).searchByName("crenvusti",null);
  assertThat(results).hasSize(5);assertThat(results.getFirst()).extracting(OpenFoodFactsClient.PackagedFoodResult::productName,OpenFoodFactsClient.PackagedFoodResult::brand,OpenFoodFactsClient.PackagedFoodResult::caloriesPer100g,OpenFoodFactsClient.PackagedFoodResult::barcode,OpenFoodFactsClient.PackagedFoodResult::sourceUrl,OpenFoodFactsClient.PackagedFoodResult::matchQuality).containsExactly("Crenvusti","Prima",250,"12345678","https://world.openfoodfacts.org/product/12345678","EXACT");server.verify();
 }
 @Test void returnsNoResultForBlankNameOrProviderFailure(){assertThat(new OpenFoodFactsClient(RestClient.create()).searchByName(" ",null)).isEmpty();assertThat(new OpenFoodFactsClient(RestClient.create()).searchByName("crenvusti",null)).isEmpty();}
}
