#include <Wire.h>
#include <AFMotor.h>
#include <FlowMeter.h>
#include <PID_v1.h>
#include <Servo.h>
#include <ArduinoJson.h> // Para manejar JSON

// Definitions
#define compass_address 0x1E
#define compass_XY_excitation 1160
#define compass_Z_excitation 1080
#define compass_rad2degree 57.3

// Variables para la brújula
float compass_x_offset = 0, compass_y_offset = 0, compass_z_offset = 0, compass_gain_fact = 1;
float compass_x_scalled, compass_y_scalled, compass_z_scalled;
float compass_x_gainError = 1, compass_y_gainError = 1, compass_z_gainError = 1, bearing = 0;
int compass_x = 0, compass_y = 0, compass_z = 0;


bool calibrating_compass = false;

// Motores y servos
AF_DCMotor motorA(2); // Motor angular
AF_DCMotor motorX(3); // Motor lineal
AF_DCMotor motorV(1); // Bomba
Servo servoH, servoV;

// Calibración del sistema
float stepsPerMM = 1000.0;
float stepsPerDegree = 10.0;
float flowCalibFactor = 1.0;
float flowVolume = 0.0;

// Pines y límites
const int pinLimMinX = 37;
const int pinLimMinA = 32;
const int pinLimMinV = 13;
int distanceCounter = 0, angleCounter = 0;
unsigned long lastUpdateTimeX = 0, lastUpdateTimeAngle = 0;
unsigned long lastUpdateTimeFlow = 0, lastUpdateTimeDatos = 0;

// Control de PID
double A_Requerido = 0, inputA = 0, EMA = 0;
double kpA = 1, kiA = 1, kdA = 0.2;
PID myPIDA(&inputA, &EMA, &A_Requerido, kpA, kiA, kdA, DIRECT);

double X_Requerido = 0, inputX = 0, EMX = 0;
double kpX = 1, kiX = 1, kdX = 0.2;
PID myPIDX(&inputX, &EMX, &X_Requerido, kpX, kiX, kdX, DIRECT);

double Vel_Requerida = 0, inputV = 0, EMV = 0;
double kpV = 15, kiV = 0, kdV = 0;
PID myPIDV(&inputV, &EMV, &Vel_Requerida, kpV, kiV, kdV, DIRECT);

// Modo manual
bool modoManual = false;
int manualMotorA = 0, manualMotorX = 0, manualMotorV = 0;

// Medidor de flujo
FlowMeter *meter;

void setup() {
    Serial.begin(115200);
    Wire.begin();
    
    // Inicialización de servos, motores y PID
    iniciarMotores();
    iniciarServos();
    iniciarFlowMeter();
    iniciarBrujula();

    // Establecer límites para PID
    myPIDA.SetOutputLimits(-255, 255);
    myPIDX.SetOutputLimits(-255, 255);
    myPIDV.SetOutputLimits(-255, 255);

    myPIDA.SetMode(AUTOMATIC);
    myPIDX.SetMode(AUTOMATIC);
    myPIDV.SetMode(AUTOMATIC);
}

void loop() {
    recibirDatos();           // Recibir datos de entrada
    leerSensores();           // Leer todos los sensores
    actualizarControlMotores(); // Controlar motores en base al modo (manual o PID)
    enviarDatos();            // Enviar datos a través del puerto serial
}

// Funciones de inicialización
void iniciarMotores() {
    motorA.setSpeed(255);
    motorA.run(RELEASE);
    motorX.setSpeed(255);
    motorX.run(RELEASE);
    motorV.setSpeed(255);
    motorV.run(RELEASE);
}

void iniciarServos() {
    servoH.attach(9);
    servoV.attach(10);
    servoH.write(0);
    servoV.write(0);
}

void iniciarFlowMeter() {
    meter = new FlowMeter(digitalPinToInterrupt(2), UncalibratedSensor, MeterISR, RISING);
    pinMode(pinLimMinV, INPUT_PULLUP);
}

void iniciarBrujula() {
    compass_x_offset = 122.17;
    compass_y_offset = 230.08;
    compass_z_offset = 389.85;
    compass_x_gainError = 1.12;
    compass_y_gainError = 1.13;
    compass_z_gainError = 1.03;
    compass_init(2); // Inicializar brújula con ganancia 2
}

// ISR para el medidor de flujo
void MeterISR() {
    meter->count();
}

// Lectura de sensores
void leerSensores() {
    leerDistancia();
    leerAngulo();
    leerBrujula();
}



void leerDistancia() {
    int XState = digitalRead(42); // Encoder A para X
    int XLimitState = digitalRead(pinLimMinX);

    if (XState != digitalRead(40)) {
        distanceCounter += (digitalRead(40) != XState) ? 1 : -1;
    }
    
    if (XLimitState) {
        distanceCounter = 0;
    }
    inputX = distanceCounter / stepsPerMM;
}

void leerAngulo() {
    int AState = digitalRead(50); // Encoder A para A
    int ALimitState = digitalRead(pinLimMinA);

    if (AState != digitalRead(48)) {
        angleCounter += (digitalRead(48) != AState) ? 1 : -1;
    }

    if (ALimitState) {
        angleCounter = 0;
    }
    inputA = angleCounter / stepsPerDegree;
}

// Control de los motores
void actualizarControlMotores() {
    if (!modoManual) {
        controlar_motores_PID();
    } else {
        controlar_motores_manual();
    }
}

void controlar_motores_manual() {
    motorA.setSpeed(abs(manualMotorA));
    motorX.setSpeed(abs(manualMotorX));
    motorV.setSpeed(abs(manualMotorV));

    motorA.run(manualMotorA > 0 ? FORWARD : BACKWARD);
    motorX.run(manualMotorX > 0 ? FORWARD : BACKWARD);
    motorV.run(manualMotorV > 0 ? FORWARD : RELEASE);
}

void controlar_motores_PID() {
    myPIDA.Compute();
    myPIDX.Compute();
    myPIDV.Compute();

    motorA.run(mapOutput(EMA) > 0 ? FORWARD : BACKWARD);
    motorX.run(mapOutput(EMX) > 0 ? FORWARD : BACKWARD);
    motorV.run(mapOutput(EMV) > 0 ? FORWARD : RELEASE);
}

int mapOutput(double output) {
    if (output > 0) return map(output, 0, 255, 70, 255);
    if (output < 0) return map(output, -255, 0, -255, -70);
    return 0;
}

// Enviar y recibir datos
void enviarDatos() {
    StaticJsonDocument<512> doc;
    
    // Sensores
    JsonObject sensors = doc.createNestedObject("sensors");
    sensors["inX"] = inputX;
    sensors["inA"] = inputA;
    sensors["inV"] = inputV;
    sensors["flowVol"] = flowVolume;
    sensors["bearing"] = bearing;

    // Actuadores
    JsonObject actuators = doc.createNestedObject("actuators");
    actuators["energia_motor_corredera"] = manualMotorX;
    actuators["energia_motor_angulo"] = manualMotorA;
    actuators["energia_motor_valvula"] = manualMotorV;
    actuators["manualMode"] = modoManual;
    
    // Valores de PID
    JsonObject pidValues = doc.createNestedObject("pidValues");
    pidValues["pid_corredera_Kp"] = kpX;
    pidValues["pid_corredera_Ki"] = kiX;
    pidValues["pid_corredera_Kd"] = kdX;
    pidValues["pid_angle_Kp"] = kpA;
    pidValues["pid_angle_Ki"] = kiA;
    pidValues["pid_angle_Kd"] = kdA;
    pidValues["pid_valve_Kp"] = kpV;
    pidValues["pid_valve_Ki"] = kiV;
    pidValues["pid_valve_Kd"] = kdV;

    // Calibración
    JsonObject calibration = doc.createNestedObject("calibration");
    calibration["stepsPerMM"] = stepsPerMM;
    calibration["stepsPerDegree"] = stepsPerDegree;
    calibration["flowCalibFactor"] = flowCalibFactor;
    
    serializeJson(doc, Serial);
    Serial.println();
}

void recibirDatos() {
    if (Serial.available()) {
        String comando = Serial.readStringUntil('\n');
        procesarComando(comando);
    }
}

void procesarComando(String comando) {
    StaticJsonDocument<512> doc;
    DeserializationError error = deserializeJson(doc, comando);
    if (error) return;

    JsonObject actuators = doc["actuators"];
    modoManual = actuators["manualMode"];
    
    manualMotorA = actuators["energia_motor_angulo"];
    manualMotorX = actuators["energia_motor_corredera"];
    manualMotorV = actuators["energia_motor_valvula"];
    
    X_Requerido = actuators["setSlide"];
    A_Requerido = actuators["setAngle"];
    Vel_Requerida = actuators["setWater"];
    
    if (actuators["resetMotorX"]) resetMotorX();
    if (actuators["resetMotorA"]) resetMotorA();
    if (actuators["calibrateCompass"]) compass_offset_calibration();

    JsonObject pidValues = doc["pidValues"];
    kpX = pidValues["pid_corredera_Kp"];
    kiX = pidValues["pid_corredera_Ki"];
    kdX = pidValues["pid_corredera_Kd"];
    kpA = pidValues["pid_angle_Kp"];
    kiA = pidValues["pid_angle_Ki"];
    kdA = pidValues["pid_angle_Kd"];
    kpV = pidValues["pid_valve_Kp"];
    kiV = pidValues["pid_valve_Ki"];
    kdV = pidValues["pid_valve_Kd"];

    myPIDX.SetTunings(kpX, kiX, kdX);
    myPIDA.SetTunings(kpA, kiA, kdA);
    myPIDV.SetTunings(kpV, kiV, kdV);

    JsonObject calibration = doc["calibration"];
    stepsPerMM = calibration["stepsPerMM"];
    stepsPerDegree = calibration["stepsPerDegree"];
    flowCalibFactor = calibration["flowCalibFactor"];
}
void MoverMotorV(int output) {
    output = constrain(output, 0, 255);
    motorV.setSpeed(output);
    if (output > 0) {
        motorV.run(FORWARD);
    } else {
        motorV.run(RELEASE);
    }
}

// Funciones de reset y calibración
void resetMotorX() {
    while (digitalRead(pinLimMinX) == LOW) {
        motorX.setSpeed(100);
        motorX.run(BACKWARD);
        delay(10);
    }
    motorX.run(RELEASE);
    distanceCounter = 0;
}

void resetMotorA() {
    while (digitalRead(pinLimMinA) == LOW) {
        motorA.setSpeed(255);
        motorA.run(BACKWARD);
        delay(10);
    }
    motorA.run(RELEASE);
    angleCounter = 0;
}

void compass_offset_calibration() {
    Serial.println("Calibrando brújula...");
    bool movingForward = true;
    int vueltasCompletadas = 0, pasosDesdeInicio = 0;

    float x_max = -4000, y_max = -4000, z_max = -4000;
    float x_min = 4000, y_min = 4000, z_min = 4000;

    while (vueltasCompletadas < 2) {
        leerAngulo();
        pasosDesdeInicio++;

        if (movingForward) {
            motorA.run(FORWARD);
        } else {
            motorA.run(BACKWARD);
        }

        if (digitalRead(pinLimMinA) == HIGH && pasosDesdeInicio > 500) {
            movingForward = !movingForward;
            pasosDesdeInicio = 0;
            vueltasCompletadas++;
        }

        leerBrujula();

        x_max = max(x_max, compass_x_offset);
        y_max = max(y_max, compass_y_offset);
        z_max = max(z_max, compass_z_offset);
        x_min = min(x_min, compass_x_offset);
        y_min = min(y_min, compass_y_offset);
        z_min = min(z_min, compass_z_offset);

        delay(10);
    }
    
    motorA.run(RELEASE);
    compass_x_offset = ((x_max - x_min) / 2) - x_max;
    compass_y_offset = ((y_max - y_min) / 2) - y_max;
    compass_z_offset = ((z_max - z_min) / 2) - z_max;
    Serial.println("Calibración completada.");
}

void compass_scalled_reading() {
    compass_read_XYZdata();
    compass_x_scalled = compass_x * compass_gain_fact * compass_x_gainError + compass_x_offset;
    compass_y_scalled = compass_y * compass_gain_fact * compass_y_gainError + compass_y_offset;
    compass_z_scalled = compass_z * compass_gain_fact * compass_z_gainError + compass_z_offset;
}

void compass_heading() {
    compass_scalled_reading();
    if (compass_y_scalled > 0) {
        bearing = 90 - atan(compass_x_scalled / compass_y_scalled) * compass_rad2degree;
    } else if (compass_y_scalled < 0) {
        bearing = 270 - atan(compass_x_scalled / compass_y_scalled) * compass_rad2degree;
    } else if (compass_y_scalled == 0 && compass_x_scalled < 0) {
        bearing = 180;
    } else {
        bearing = 0;
    }
}
void compass_read_XYZdata() {
    Wire.beginTransmission(compass_address);
    Wire.write(0x02);
    Wire.write(0b10000001);
    Wire.endTransmission();
    Wire.requestFrom(compass_address, 6);

    if (6 <= Wire.available()) {
        compass_x = Wire.read() << 8 | Wire.read();
        compass_z = Wire.read() << 8 | Wire.read();
        compass_y = Wire.read() << 8 | Wire.read();
    }
}
// Inicialización y configuración de brújula
void compass_init(int gain) {
    byte gain_reg;
    Wire.beginTransmission(compass_address);
    Wire.write(0x01);
    
    switch(gain) {
        case 0: gain_reg = 0b00000000; compassGainFactors[0] = 0.73; break;
        case 1: gain_reg = 0b00100000; compassGainFactors[0] = 0.92; break;
        case 2: gain_reg = 0b01000000; compassGainFactors[0] = 1.22; break;
        case 3: gain_reg = 0b01100000; compassGainFactors[0] = 1.52; break;
        case 4: gain_reg = 0b10000000; compassGainFactors[0] = 2.27; break;
        case 5: gain_reg = 0b10100000; compassGainFactors[0] = 2.56; break;
        case 6: gain_reg = 0b11000000; compassGainFactors[0] = 3.03; break;
        case 7: gain_reg = 0b11100000; compassGainFactors[0] = 4.35; break;
    }
    
    Wire.write(gain_reg);
    Wire.write(0b00000011);
    Wire.endTransmission();
    Serial.print("Gain updated to  = ");
    Serial.println(compassGainFactors[0]);
}
