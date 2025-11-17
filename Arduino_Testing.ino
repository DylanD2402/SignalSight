const int ledButton = 2;
const int piezoButton = 3;
const int led = 13;
const int piezo = 9;

bool ledState = false;
bool piezoState = false;

void setup() {
  pinMode(ledButton, INPUT_PULLUP);
  pinMode(piezoButton, INPUT_PULLUP);
  pinMode(led, OUTPUT);
  pinMode(piezo, OUTPUT);
}

void loop() {
//Toggle LED
  if (digitalRead(ledButton)==LOW){
    delay(100);
    if(digitalRead(ledButton)==LOW){
      ledState =!ledState;
      digitalWrite(led, ledState);
      while(digitalRead(ledButton)==LOW);
    }
  }

  //Toggle Piezo
  if(digitalRead(piezoButton)==LOW){
    delay(100);
    if(digitalRead(piezoButton)==LOW){
      piezoState = !piezoState;
      if(piezoState){
        tone(piezo, 2000);
      }
      else{
        noTone(piezo);
      }
      while(digitalRead(piezoButton)==LOW);
    }
  }

}
