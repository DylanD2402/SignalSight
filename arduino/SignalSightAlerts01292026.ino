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

// Fast red-beep settings (after escalation)
const int red_beep_frequency      = 2000;
const unsigned long red_beep_on   = 120;
const unsigned long red_beep_off  = 120;

// Yellow-beep settings (also used as "slow red" at first)
const int yellow_beep_frequency     = 1500;
const unsigned long yellow_beep_on  = 200;
const unsigned long yellow_beep_off = 800;

// Green tone (used when "no acceleration" detected)
const int green_beep_frequency        = 1200;
const unsigned long GREEN_DURATION_MS = 5000;

// Green rule: if speed doesn't increase after 3s, start beeping
const unsigned long GREEN_NO_ACCEL_MS = 3000;

const unsigned long DEBOUNCE_MS = 35;

// ================== All-3-buttons FAULT chord ============
const unsigned long ALL3_TRIGGER_MS = 150;   // enter fault
const unsigned long ALL3_EXIT_MS    = 1500;  // exit fault

unsigned long all3DownSince = 0;
bool all3ActionTaken = false;

// ================== Speed / Distance from Pi ============
int speedKmh = -1;   // integer km/h from Pi
int distM    = -1;   // integer metres from Pi

// (still useful for debugging/other future logic)
int lastSpeedKmh = -1;
unsigned long speedStableSince = 0;  // when speed last changed

// Red escalation tracking
unsigned long redEnteredAt = 0;
int redSpeedAtEntry = -1;
bool redFastBeep = false;

// Green tracking (NEW)
unsigned long greenStart = 0;
unsigned long greenEnteredAt = 0;
int greenSpeedAtEntry = -1;

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

  // Red escalation tracking
  redEnteredAt = millis();
  redSpeedAtEntry = speedKmh;   // snapshot
  redFastBeep = false;          // start slow

  // Start beep timing (slow pattern first)
  beepOn = false;
  tLedRed = millis();
  tBeep   = millis();
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
  tBeep   = millis();
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

  // Green LED on immediately; piezo depends on speed increase after 3s
  noTone(piezo);
  beepOn = false;

  greenStart = millis();          // auto-exit timer
  greenEnteredAt = greenStart;    // 3s "no-accel" timer
  greenSpeedAtEntry = speedKmh;   // snapshot

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
      if (b.stableState == LOW) return true; // pressed edge
    }
  }
  return false;
}

// ================== Parsing helpers =====================
bool parseKeyInt(const String &s, const String &key, int &out) {
  int k = s.indexOf(key);
  if (k < 0) return false;
  k += key.length();

  while (k < (int)s.length() && s[k] == ' ') k++;

  bool neg = false;
  if (k < (int)s.length() && s[k] == '-') { neg = true; k++; }

  long val = 0;
  bool any = false;
  while (k < (int)s.length() && isDigit(s[k])) {
    any = true;
    val = val * 10 + (s[k] - '0');
    k++;
  }
  if (!any) return false;
  out = neg ? -val : val;
  return true;
}

void onSpeedUpdated(unsigned long now) {
  if (speedKmh != lastSpeedKmh) {
    lastSpeedKmh = speedKmh;
    speedStableSince = now;
  }
}

// ================== Pi Serial parsing ===================
void processPiStateLine(const String &line) {
  String s = line;
  s.trim();
  if (s.length() == 0) return;

  unsigned long now = millis();

  // Update speed/dist whenever present (even if state repeats)
  int tmp;
  if (parseKeyInt(s, "SPEED=", tmp)) { speedKmh = tmp; onSpeedUpdated(now); }
  if (parseKeyInt(s, "DIST=",  tmp)) { distM  = tmp; }

  // Determine state token
  String stateToken = "";

  int st = s.indexOf("STATE=");
  if (st >= 0) {
    int start = st + 6;
    int end = s.indexOf(' ', start);
    if (end < 0) end = s.length();
    stateToken = s.substring(start, end);
    stateToken.trim();
  } else {
    // If the entire line is just a state (legacy behavior)
    if (s == "ACTIVE_RED" || s == "ACTIVE_YELLOW" || s == "ACTIVE_GREEN" || s == "IDLE" || s == "FAULT") {
      stateToken = s;
    } else {
      // Only SPEED=... or DIST=... etc -> no state change
      return;
    }
  }

  // Don’t re-enter same state; just ignore transition if same
  if (stateToken == lastPiState) return;
  lastPiState = stateToken;

  if (stateToken == "ACTIVE_RED") {
    enterRed();
  }
  else if (stateToken == "ACTIVE_YELLOW") {
    enterYellow();
  }
  else if (stateToken == "ACTIVE_GREEN") {
    // NOTE: We no longer require speed==0 to ENTER green.
    // The "no speed increase after 3s" rule is handled inside green_mode.
    enterGreen();
  }
  else if (stateToken == "IDLE") {
    enterIdle();
  }
  else if (stateToken == "FAULT") {
    enterFault();
  }
}

void pollPiSerial() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n') {
      processPiStateLine(piLine);
      piLine = "";
    } else if (c != '\r') {
      if (piLine.length() < 96) piLine += c;
      else piLine = ""; // overflow safety
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

  speedStableSince = millis();
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
    else if (grnPress) enterGreen(); // allow green always; beep rule handled in green_mode
  }

  switch (mode) {

    case red_mode: {
      // LED blink fast
      if (now - tLedRed >= red_blink_fast) {
        redLedOn = !redLedOn;
        digitalWrite(led_red, redLedOn);
        tLedRed = now;
      }

      // After 2s, if speed did NOT decrease, go fast
      if (!redFastBeep && (now - redEnteredAt >= 2000)) {
        if (redSpeedAtEntry >= 0 && speedKmh >= 0) {
          if (speedKmh >= redSpeedAtEntry) redFastBeep = true;
        } else {
          // If speed missing, assume no deceleration -> fast beep
          redFastBeep = true;
        }
      }

      // Slow (yellow) first, fast (red) after escalation
      int freq = redFastBeep ? red_beep_frequency : yellow_beep_frequency;
      unsigned long onT  = redFastBeep ? red_beep_on  : yellow_beep_on;
      unsigned long offT = redFastBeep ? red_beep_off : yellow_beep_off;

      if (beepOn) {
        if (now - tBeep >= onT) {
          beepOn = false;
          noTone(piezo);
          tBeep = now;
        }
      } else {
        if (now - tBeep >= offT) {
          beepOn = true;
          tone(piezo, freq);
          tBeep = now;
        }
      }
      break;
    }

    case yellow_mode: {
      // Yellow blink medium
      if (now - tLedYel >= yellow_blink_medium) {
        yelLedOn = !yelLedOn;
        digitalWrite(led_yellow, yelLedOn);
        tLedYel = now;
      }

      // Beep only if within 100m
      bool within100 = (distM >= 0 && distM <= 100);

      if (!within100) {
        noTone(piezo);
        beepOn = false;
        tBeep = now; // reset cadence
        break;
      }

      // Yellow beep pattern
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
    }

    case green_mode: {
      digitalWrite(led_green, HIGH);

      // After 3 seconds in green start beeping IF speed did NOT increase
      bool after3s = (now - greenEnteredAt >= GREEN_NO_ACCEL_MS);

      // not increased then
      bool notIncreased =
        (speedKmh < 0) || (greenSpeedAtEntry < 0) || (speedKmh <= greenSpeedAtEntry);

      if (after3s && notIncreased) {
        tone(piezo, green_beep_frequency);
      } else {
        noTone(piezo);
      }

      // Auto-exit based on time (to be changed to speed detection)
      if (now - greenStart >= GREEN_DURATION_MS) {
        enterIdle();
      }
      break;
    }

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