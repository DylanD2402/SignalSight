#include <LiquidCrystal.h>

// ================== LCD wiring (4-bit) ==================
// RS, E, D4, D5, D6, D7  (LCD D4-D7 map to Arduino D5,D4,D3,D2)
LiquidCrystal lcd(12, 11, 5, 4, 3, 2);

// ================== Pin assignments =====================
const int button_red    = 6;   // Buttons (active LOW with INPUT_PULLUP)
const int button_yellow    = 8;
const int button_green    = 10;

const int led_red    = 7;   // LEDs (through 220 Ω resistors to GND)
const int led_yellow    = 9;
const int led_green    = 13;  // Note: on-board LED also on D13

const int piezo      = A0;  // Piezo buzzer (+ to A0, − to GND)

// ================== Behavior tuning =====================
// LED blink speeds
const unsigned long red_blink_fast = 200;   // fast blink
const unsigned long yellow_blink_medium = 600;   // slow blink

// Piezo beep patterns
const int red_beep_frequency = 2000;
const unsigned long red_beep_on  = 120;
const unsigned long red_beep_off = 120;

const int yellow_beep_frequency = 1500;
const unsigned long yellow_beep_on  = 200;
const unsigned long yellow_beep_off = 800;

const int green_beep_frequency = 1200;               // continuous tone for green
const unsigned long GREEN_DURATION_MS = 5000;     // 5 seconds

// Debounce
const unsigned long DEBOUNCE_MS = 35;

// ================== State machine =======================
enum Mode { IDLE, red_mode, yellow_mode, green_mode };
Mode mode = IDLE;

// Button debouncing
struct ButtonDebounce {
  const int pin;
  int lastReading;
  int stableState;
  unsigned long lastChangeTime;
};
ButtonDebounce btns[3] = {
  { button_red, HIGH, HIGH, 0 },
  { button_yellow, HIGH, HIGH, 0 },
  { button_green, HIGH, HIGH, 0 }
};

// Timers/flags
unsigned long tLedRed = 0;  bool redLedOn = false;
unsigned long tLedYel = 0;  bool yelLedOn = false;

unsigned long tBeep   = 0;  bool beepOn   = false;
unsigned long greenStart = 0;

// ================== Helpers =============================
void showIdle() {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("System Ready");
  lcd.setCursor(0, 1);
  lcd.print("Press a button");
}

void enterRed() {
  mode = red_mode;
  digitalWrite(led_red, LOW);
  digitalWrite(led_yellow, LOW);
  digitalWrite(led_green, LOW);
  redLedOn = false;
  tLedRed = millis();

  beepOn = false;
  tBeep = millis();
  noTone(piezo);

  lcd.clear();
  lcd.setCursor(0, 0); lcd.print("RED LIGHT!");
  lcd.setCursor(0, 1); lcd.print("STOP! STOP!");
}

void enterYellow() {
  mode = yellow_mode;
  digitalWrite(led_red, LOW);
  digitalWrite(led_yellow, LOW);
  digitalWrite(led_green, LOW);
  yelLedOn = false;
  tLedYel = millis();

  beepOn = false;
  tBeep = millis();
  noTone(piezo);

  lcd.clear();
  lcd.setCursor(0, 0); lcd.print("YELLOW LIGHT!");
  lcd.setCursor(0, 1); lcd.print("SLOW DOWN!");
}

void enterGreen() {
  mode = green_mode;
  digitalWrite(led_red, LOW);
  digitalWrite(led_yellow, LOW);
  digitalWrite(led_green, HIGH);

  tone(piezo, green_beep_frequency);
  greenStart = millis();

  lcd.clear();
  lcd.setCursor(0, 0); lcd.print("GREEN LIGHT!");
  lcd.setCursor(0, 1); lcd.print("GO! START MOVING");
}

void enterIdle() {
  mode = IDLE;
  digitalWrite(led_red, LOW);
  digitalWrite(led_yellow, LOW);
  digitalWrite(led_green, LOW);
  noTone(piezo);
  showIdle();
}

// Returns true once on press (falling edge)
bool buttonPressedEdge(int idx) {
  ButtonDebounce &b = btns[idx];
  int reading = digitalRead(b.pin);
  if (reading != b.lastReading) {
    b.lastChangeTime = millis();
    b.lastReading = reading;
  }
  if (millis() - b.lastChangeTime > DEBOUNCE_MS) {
    if (b.stableState != reading) {
      b.stableState = reading;
      if (b.stableState == LOW) {
        return true; // pressed (active LOW)
      }
    }
  }
  return false;
}

// ================== Arduino setup/loop ==================
void setup() {
  pinMode(led_red, OUTPUT);
  pinMode(led_yellow, OUTPUT);
  pinMode(led_green, OUTPUT);

  pinMode(button_red, INPUT_PULLUP);
  pinMode(button_yellow, INPUT_PULLUP);
  pinMode(button_green, INPUT_PULLUP);

  pinMode(piezo, OUTPUT);

  lcd.begin(16, 2);
  enterIdle();
}

void loop() {
  // Read button edges
  bool redPress = buttonPressedEdge(0);
  bool yelPress = buttonPressedEdge(1);
  bool grnPress = buttonPressedEdge(2);

  // If we're idle, a press selects a mode; if we're in any mode, ANY press cancels to idle
  if (mode == IDLE) {
    if (redPress)      enterRed();
    else if (yelPress) enterYellow();
    else if (grnPress) enterGreen();
  } else {
    if (redPress || yelPress || grnPress) {
      enterIdle();
      return; // skip running mode logic this loop
    }
  }

  unsigned long now = millis();

  // --- Mode behaviors ---
  switch (mode) {
    case red_mode:
      // Red LED fast blink
      if (now - tLedRed >= red_blink_fast) {
        redLedOn = !redLedOn;
        digitalWrite(led_red, redLedOn);
        digitalWrite(led_yellow, LOW);
        digitalWrite(led_green, LOW);
        tLedRed = now;
      }
      // Piezo fast intermittent
      if (beepOn) {
        if (now - tBeep >= red_beep_on) {
          beepOn = false;
          noTone(piezo);
          tBeep = now;
        }
      } else {
        if (now - tBeep >= red_beep_off) {
          beepOn = true;
          tone(piezo, red_beep_frequency);
          tBeep = now;
        }
      }
      break;

    case yellow_mode:
      // Yellow LED slow blink
      if (now - tLedYel >= yellow_blink_medium) {
        yelLedOn = !yelLedOn;
        digitalWrite(led_yellow, yelLedOn);
        digitalWrite(led_red, LOW);
        digitalWrite(led_green, LOW);
        tLedYel = now;
      }
      // Piezo slow intermittent
      if (beepOn) {
        if (now - tBeep >= yellow_beep_on) {
          beepOn = false;
          noTone(piezo);
          tBeep = now;
        }
      } else {
        if (now - tBeep >= yellow_beep_off) {
          beepOn = true;
          tone(piezo, yellow_beep_frequency);
          tBeep = now;
        }
      }
      break;

    case green_mode:
      // Solid green, continuous tone
      digitalWrite(led_red, LOW);
      digitalWrite(led_yellow, LOW);
      digitalWrite(led_green, HIGH);
      tone(piezo, green_beep_frequency);
      // Auto-exit after 5 s
      if (now - greenStart >= GREEN_DURATION_MS) {
        enterIdle();
      }
      break;

    case IDLE:
    default:
      // All off (handled in enterIdle)
      break;
  }
}