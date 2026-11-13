// =====================================================================
// ArcticChain S-Mite firmware — ESP32-S3 + SX1262 LoRa swarm node
//
// Role: perchable environmental sensing bee. Perch-and-report energy
// model: deep sleep between measurement/report cycles, solar assist.
//
// Hardware (see docs/print/02_S_Mite.pdf):
//   ESP32-S3 dev module, E22-900M30S (SX1262) LoRa 915 MHz,
//   BME280 (temp/hum/pressure), SGP30 (VOC/index), VL53L0X or
//   photodiode light, LiPo 800 mAh + 5V solar via TP4056.
//
// Pin map (rev A carrier):
//   LoRa NSS=8  RESET=9  BUSY=10  DIO1=11  RXEN=12
//   I2C SDA=4  SCL=5  (BME280 0x76, SGP30 0x58)
//   Light  = ADC1_CH0 (GPIO1)
//   Perch detect = GPIO2 (hall/magnet or microswitch)
//   Battery sense = ADC1_CH3 (GPIO3) via divider
//   Status LED = GPIO48 (WS2812 or plain)
//
// Behaviour:
//   1. wake -> read sensors -> build signed-ish frame -> LoRa TX
//   2. listen window for mesh traffic / pod-charger beacons
//   3. deep sleep until next cycle (or perch-removed -> relocate mode)
//   4. on Anchor dock: charge + fast report + possible firmware push
//
// Build: Arduino IDE 2.x, board "ESP32S3 Dev Module",
//        libs: RadioLib, Adafruit BME280, Adafruit SGP30, Wire.
// =====================================================================

#include <Arduino.h>
#include <Wire.h>
#include <RadioLib.h>
#include <Adafruit_BME280.h>
#include <Adafruit_SGP30.h>

// ---------------- config ----------------
#define NODE_ID        "mite-0001"     // TODO: derive from MAC + flash
#define COMMUNITY      "default"
#define LORA_FREQ      915.0           // MHz — Canada ISM
#define LORA_BW        125.0           // kHz
#define LORA_SF        9               // spreading factor (range vs airtime)
#define LORA_CR        7               // coding rate 4/8... wait: 5=4/8? use 7->4/5? RadioLib: 5..8 => 4/5..4/8
#define TX_POWER       14              // dBm (ISM legal, keep <=14 ERP-equiv)
#define SLEEP_S        300             // 5 min report cadence (solar permitting)
#define LISTEN_MS      1500            // post-TX listen window

// pins
#define PIN_LORA_NSS   8
#define PIN_LORA_RST   9
#define PIN_LORA_BUSY  10
#define PIN_LORA_DIO1  11
#define PIN_LORA_RXEN  12
#define PIN_I2C_SDA    4
#define PIN_I2C_SCL    5
#define PIN_LIGHT      1               // ADC1_CH0
#define PIN_PERCH      2               // digital in, pulled up
#define PIN_BATT       3               // ADC1_CH3 via 2:1 divider
#define PIN_LED        48

// ---------------- radio ----------------
SX1262 radio = new Module(PIN_LORA_NSS, PIN_LORA_DIO1, PIN_LORA_RST,
                          PIN_LORA_BUSY, RADIOLIB_NC, PIN_LORA_RXEN);
Adafruit_BME280 bme;
Adafruit_SGP30 sgp;
bool have_bme = false, have_sgp = false;

// ---------------- helpers ----------------
float read_battery_mv() {
  // 2:1 divider on LiPo+ -> ADC; 3.3V ref, 12-bit
  uint32_t raw = analogReadMilliVolts(PIN_BATT) * 2;
  return (float)raw;
}

uint16_t read_light() {
  return analogRead(PIN_LIGHT);       // 0..4095, higher = brighter
}

bool perched() {
  return digitalRead(PIN_PERCH) == LOW;   // magnet closes switch when docked/perched
}

void led(uint8_t r, uint8_t g, uint8_t b) {
#ifdef USE_WS2812
  // strip.begin(); strip.setPixelColor(0, strip.Color(r,g,b)); strip.show();
#else
  digitalWrite(PIN_LED, (r + g + b) > 0 ? HIGH : LOW);
#endif
}

// ---------------- frame ----------------
// Tiny telemetry frame — keep under ~50 B for LoRa airtime.
// Layout (binary, little-endian):
//   [0]    magic 'A'
//   [1]    version 1
//   [2:4]  community crc16? — keep simple: community id hash byte
//   [4:14] node id (10 chars padded)
//   [14]   role (0=sensor 1=eye 2=relay 3=charger)
//   [15]   seq
//   [16:18] temp_c x10 (int16)
//   [18:20] hum_pct x10 (uint16)
//   [20:22] voc_ppb /100 (uint16)
//   [22:24] light raw (uint16)
//   [24:26] battery mv /100 (uint16)
//   [26:28] flags (perched bit0, docked bit1)
//   [28:30] crc16-ccitt over [0..28)
// Total: 30 bytes.

uint16_t crc16_ccitt(const uint8_t *d, size_t n) {
  uint16_t crc = 0xFFFF;
  for (size_t i = 0; i < n; i++) {
    crc ^= (uint16_t)d[i] << 8;
    for (int b = 0; b < 8; b++)
      crc = (crc & 0x8000) ? (crc << 1) ^ 0x1021 : (crc << 1);
  }
  return crc;
}

uint8_t ROLE = 0;   // set per build variant: SENSOR=0 EYE=1 RELAY=2 CHARGER=3

void build_frame(uint8_t *buf) {
  memset(buf, 0, 30);
  buf[0] = 'A'; buf[1] = 1;
  buf[2] = (uint8_t)(COMMUNITY[0]);          // community tag (hash later)
  strncpy((char *)&buf[4], NODE_ID, 10);
  buf[14] = ROLE;
  static uint8_t seq = 0; buf[15] = seq++;

  float t = have_bme ? bme.readTemperature() : NAN;
  float h = have_bme ? bme.readHumidity() : NAN;
  uint16_t voc = have_sgp ? sgp.eCO2 : 0;    // SGP30 gives eCO2/VOC approx
  uint16_t li = read_light();
  uint16_t bat = (uint16_t)(read_battery_mv() / 100.0f);
  uint16_t fl = (perched() ? 1 : 0);

  if (!isnan(t)) { int16_t tv = (int16_t)(t * 10); memcpy(&buf[16], &tv, 2); }
  if (!isnan(h)) { uint16_t hv = (uint16_t)(h * 10); memcpy(&buf[18], &hv, 2); }
  memcpy(&buf[20], &voc, 2);
  memcpy(&buf[22], &li, 2);
  memcpy(&buf[24], &bat, 2);
  memcpy(&buf[26], &fl, 2);
  uint16_t c = crc16_ccitt(buf, 28);
  memcpy(&buf[28], &c, 2);
}

// ---------------- sleep ----------------
void deep_sleep_s(uint32_t sec) {
  led(0, 0, 0);
  // keep LoRa powered down; ESP32 deep sleep ~10 µA + RTC
  esp_sleep_enable_timer_wakeup((uint64_t)sec * 1000000ULL);
  esp_deep_sleep_start();
}

// ---------------- setup ----------------
void setup() {
  Serial.begin(115200);
  pinMode(PIN_LED, OUTPUT);
  pinMode(PIN_PERCH, INPUT_PULLUP);
  analogSetPinAttenuation(PIN_LIGHT, ADC_11db);
  analogSetPinAttenuation(PIN_BATT, ADC_11db);

  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);
  have_bme = bme.begin(0x76) || bme.begin(0x77);
  have_sgp = sgp.begin();
  if (have_sgp) sgp.IAQmeasure();          // prime gas sensor

  int state = radio.begin(LORA_FREQ, LORA_BW, LORA_SF, LORA_CR, TX_POWER);
  if (state != RADIOLIB_ERR_NONE) {
    Serial.printf("[lora] init fail %d — blink & sleep\n", state);
    for (int i = 0; i < 10; i++) { digitalWrite(PIN_LED, !digitalRead(PIN_LED)); delay(120); }
    deep_sleep_s(SLEEP_S);
  }
  radio.startReceive();
  Serial.println("[mite] boot ok");
}

// ---------------- loop ----------------
void loop() {
  uint8_t frame[30];
  build_frame(frame);

  // TX telemetry
  int st = radio.transmit(frame, sizeof(frame));
  if (st == RADIOLIB_ERR_NONE) {
    Serial.printf("[tx] %d B, RSSI %d\n", sizeof(frame), radio.getRSSI());
  } else {
    Serial.printf("[tx] fail %d\n", st);
  }

  // listen window — collect neighbor beacons / pod offers
  radio.startReceive();
  uint32_t listen_until = millis() + LISTEN_MS;
  bool heard = false;
  while (millis() < listen_until) {
    int irq = radio.getIrqFlags();
    if (irq & RADIOLIB_SX126X_IRQ_RX_DONE) {
      uint8_t buf[64]; size_t len = sizeof(buf);
      int r = radio.readData(buf, &len);
      if (r == RADIOLIB_ERR_NONE && len >= 30 && buf[0] == 'A') {
        heard = true;
        // TODO: parse neighbor frame -> mesh table -> relay if needed
        Serial.printf("[rx] %d B rssi %d\n", (int)len, radio.getRSSI());
      }
      radio.startReceive();
    }
    delay(5);
  }

  // energy decision: if battery low and no sun, stretch the cycle
  uint16_t bat_mv = (uint16_t)(read_battery_mv() / 1000.0f);
  uint32_t sleep_s = (bat_mv < 3400) ? SLEEP_S * 4 : SLEEP_S;

  Serial.printf("[sleep] %lus heard=%d bat=%umV\n", (unsigned long)sleep_s,
                heard, bat_mv);
  deep_sleep_s(sleep_s);   // never returns
}
