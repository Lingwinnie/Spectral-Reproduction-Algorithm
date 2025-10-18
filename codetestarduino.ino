// LEDs PINS DEFINITION
const int ledPins[6] = {3, 5, 6, 9, 10, 11};
int brightness[6] = {0, 0, 0, 0, 0, 0};

void setup() {
  Serial.begin(9600);
  for (int i = 0; i < 6; i++) {
    pinMode(ledPins[i], OUTPUT);
    analogWrite(ledPins[i], brightness[i]);
  }
}

void loop() {
  if (Serial.available()) {
    String input = Serial.readStringUntil('\n');
    input.trim(); 
// COMMAND DEFINITION
    if (input.startsWith("L") && input.indexOf(':') > 1) {
      int ledIndex = input.substring(1, input.indexOf(':')).toInt();
      int value = input.substring(input.indexOf(':') + 1).toInt();

      if (ledIndex >= 1 && ledIndex <= 6) {
        value = constrain(value, 0, 255);
        brightness[ledIndex - 1] = value;
        analogWrite(ledPins[ledIndex - 1], value);

        Serial.print("LED ");
        Serial.print(ledIndex);
        Serial.print(" -> ");
        Serial.println(value);
      } else {
        Serial.println("Erreur : index LED invalide (1 à 6).");
      }
    } else {
      Serial.println("Commande invalide. Format attendu : L1:128");
    }
  }
}
