#include <Wire.h>
#include <LiquidCrystal.h>

// ================== LCD wiring (4-bit) ==================
LiquidCrystal lcd(12, 11, 5, 4, 3, 2);

// ================== Pin assignments =====================
const int button_red    = 6;
const int button_yellow = 8;
const int button_green  = 10;

const int led_red       = 7;
const int led_yellow    = 9;
const int led_green     = 13;

const int piezo         = A0;

// ================== Behavior tuning =====================
const unsigned long red_blink_fast      = 200;
const unsigned long yellow_blink_medium = 600;

const int red_beep_frequency      = 2000;
const unsigned long red_beep_on   = 120;
const unsigned long red_beep_off  = 120;

const int yellow_beep_frequency   = 1500;
const unsigned long yellow_beep_on  = 200;
const unsigned long yellow_beep_off = 800;

const int green_beep_frequency    = 1200;
const unsigned long GREEN_DURATION_MS = 5000;

const unsigned long DEBOUNCE_MS = 35;

// ================== All-3-buttons FAULT chord ============
// Short chord (press all 3 briefly) enters FAULT
// Long chord (hold all 3) exits FAULT
const unsigned long ALL3_TRIGGER_MS = 150;   // enter fault
const unsigned long ALL3_EXIT_MS    = 1500;  // exit fault

unsigned long all3DownSince = 0;
bool all3ActionTaken = false;

// ================== State machine ========================
enum Mode { IDLE, red_mode, yellow_mode, green_mode, fault_mode };
Mode mode = IDLE;

// ================== Button debouncing ====================
struct ButtonDebounce {
  const int pin;
  int lastReading;
  int stableState;
  unsigned long lastChangeTime;
};

ButtonDebounce btns[3] = {
  { button_red,    HIGH, HIGH, 0 },
  { button_yellow, HIGH, HIGH, 0 },
  { button_green,  HIGH, HIGH, 0 }
};

// ================== Timers / flags ======================
unsigned long tLedRed = 0;  bool redLedOn = false;
unsigned long tLedYel = 0;  bool yelLedOn = false;
unsigned long tBeep   = 0;  bool beepOn   = false;
unsigned long greenStart = 0;

// ================== Pi Serial ===========================
String piLine = "";
String lastPiState = "";

// ================== UI Helpers ===========================
void showIdle() {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("System Ready");
  lcd.setCursor(0, 1);
  lcd.print("Waiting...");
}

void enterFault() {
  mode = fault_mode;

  // Requirements:
  // - LCD: "CAMERA SYSTEM DOWN"
  // - All 3 LEDs ON
  // - No piezo
  noTone(piezo);
  beepOn = false;

  digitalWrite(led_red, HIGH);
  digitalWrite(led_yellow, HIGH);
  digitalWrite(led_green, HIGH);

  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("CAMERA SYSTEM");
  lcd.setCursor(0, 1);
  lcd.print("DOWN");
}

void enterRed() {
  mode = red_mode;
  digitalWrite(led_red, LOW);
  digitalWrite(led_yellow, LOW);
  digitalWrite(led_green, LOW);
  redLedOn = false;

  beepOn = false;
  tLedRed = millis();
  tBeep = millis();
  noTone(piezo);

  lcd.clear();
  lcd.setCursor(0, 0); lcd.print("RED LIGHT!");
  lcd.setCursor(0, 1); lcd.print("STOP!");
}

void enterYellow() {
  mode = yellow_mode;
  digitalWrite(led_red, LOW);
  digitalWrite(led_yellow, LOW);
  digitalWrite(led_green, LOW);
  yelLedOn = false;

  beepOn = false;
  tLedYel = millis();
  tBeep = millis();
  noTone(piezo);

  lcd.clear();
  lcd.setCursor(0, 0); lcd.print("YELLOW!");
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
  lcd.setCursor(0, 0); lcd.print("GREEN!");
  lcd.setCursor(0, 1); lcd.print("GO!");
}

void enterIdle() {
  mode = IDLE;
  digitalWrite(led_red, LOW);
  digitalWrite(led_yellow, LOW);
  digitalWrite(led_green, LOW);
  noTone(piezo);
  beepOn = false;
  showIdle();
}

// ================== Button logic ========================
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
      if (b.stableState == LOW) return true;
    }
  }
  return false;
}

// ================== Pi Serial parsing ===================
void processPiStateLine(const String &line) {
  String s = line;
  s.trim();
  if (s.length() == 0) return;

  if (s == lastPiState) return;
  lastPiState = s;

  if (s == "ACTIVE_RED")          enterRed();
  else if (s == "ACTIVE_YELLOW")  enterYellow();
  else if (s == "ACTIVE_GREEN")   enterGreen();
  else if (s == "IDLE")           enterIdle();
  else if (s == "FAULT")          enterFault();
}

void pollPiSerial() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n') {
      processPiStateLine(piLine);
      piLine = "";
    } else if (c != '\r') {
      if (piLine.length() < 64) piLine += c;
      else piLine = "";
    }
  }
}

// ================== Setup ===============================
void setup() {
  Serial.begin(115200);

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

// ================== Loop ================================
void loop() {
  pollPiSerial();

  // ---- All-3 chord detection (raw reads, independent of debounce) ----
  bool rDown = (digitalRead(button_red) == LOW);
  bool yDown = (digitalRead(button_yellow) == LOW);
  bool gDown = (digitalRead(button_green) == LOW);
  bool all3Down = rDown && yDown && gDown;

  unsigned long now = millis();

  if (all3Down) {
    if (all3DownSince == 0) {
      all3DownSince = now;
      all3ActionTaken = false;
    }

    unsigned long held = now - all3DownSince;

    // In FAULT: long-hold exits with manual override message
    if (mode == fault_mode && !all3ActionTaken && held >= ALL3_EXIT_MS) {
      lcd.clear();
      lcd.setCursor(0,0);
      lcd.print("Manual Exit");
      delay(600);
      enterIdle();
      all3ActionTaken = true;
      return;
    }

    // Not in FAULT: short chord enters FAULT
    if (mode != fault_mode && !all3ActionTaken && held >= ALL3_TRIGGER_MS) {
      enterFault();
      all3ActionTaken = true;
      return;
    }
  } else {
    all3DownSince = 0;
    all3ActionTaken = false;
  }

  // Debounced single-press edges
  bool redPress = buttonPressedEdge(0);
  bool yelPress = buttonPressedEdge(1);
  bool grnPress = buttonPressedEdge(2);

  // ---- MANUAL EXIT (any button during active mode) ----
  // Do NOT allow exiting FAULT with single buttons
  if (mode != IDLE && mode != fault_mode && (redPress || yelPress || grnPress)) {
    lcd.clear();
    lcd.setCursor(0,0);
    lcd.print("Manual Exit");
    delay(600);
    enterIdle();
    return;
  }

  // ---- Trigger from IDLE ----
  // Ignore normal triggers if all three buttons are held (prevents accidental mode change)
  if (mode == IDLE && !all3Down) {
    if (redPress)      enterRed();
    else if (yelPress) enterYellow();
    else if (grnPress) enterGreen();
  }

  switch (mode) {
    case red_mode:
      if (now - tLedRed >= red_blink_fast) {
        redLedOn = !redLedOn;
        digitalWrite(led_red, redLedOn);
        tLedRed = now;
      }
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
      if (now - tLedYel >= yellow_blink_medium) {
        yelLedOn = !yelLedOn;
        digitalWrite(led_yellow, yelLedOn);
        tLedYel = now;
      }
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
      digitalWrite(led_green, HIGH);
      if (now - greenStart >= GREEN_DURATION_MS) {
        enterIdle();
      }
      break;

    case fault_mode:
      // Latched FAULT outputs (re-assert every loop)
      digitalWrite(led_red, HIGH);
      digitalWrite(led_yellow, HIGH);
      digitalWrite(led_green, HIGH);
      noTone(piezo);
      beepOn = false;
      break;

    case IDLE:
    default:
      break;
  }
}
