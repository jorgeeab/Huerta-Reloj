
#include <AFMotor.h>
#include <FlowMeter.h>
#include <PID_v1.h>
#include <ArduinoJson.h> // Para manejar JSON

// Motores
AF_DCMotor motorA(2); // Motor angular
AF_DCMotor motorX(3); // Motor lineal
AF_DCMotor motorV(1); // Bomba (solo hacia adelante)

// Calibración del sistema
float stepsPerMM = 1000.0;
float stepsPerDegree = 10.0;
float flowCalibFactor = 1.0;
float flowVolume = 0.0;

// Límites
const int limMinX = 0;    // Límite mínimo en mm para corredera
const int limMaxX = 400;  // Límite máximo en mm para corredera
const int limMinA = 0;    // Límite mínimo en grados para ángulo
const int limMaxA = 360;  // Límite máximo en grados para ángulo

// Límites del brazo
const int PinLimMinX = 37;
#define outputB_X 40
#define outputA_X 42
int distance_counter = 0;
int XState = 0;
int XLastState = 0;
int XLimit_State = 0;

#define outputB_A 48
#define outputA_A 50
const int pinLimMinA = 32;
int angle_counter = 0;
int AState = 0;
int ALastState = 0;
int ALimit_State = 0;
// Bandera de calibración
bool calibrandoX = false;
bool calibrandoA = false;
unsigned long previousMillis = 0;
const long interval = 300; // Interval in milliseconds

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
int manualMotorA = 0, manualMotorX = 0, manualMotorV = 0; // Bomba solo va hacia adelante

FlowMeter *Meter;
const unsigned long period = 100;
unsigned long lastUpdateTimeFlow = 0;
const long updateIntervalFlowPID = 100;

void setup() {
    Serial.begin(115200);

    // Inicialización de motores y PID
    iniciarMotores();
    iniciarFlowMeter();

    // Establecer límites para PID
    myPIDA.SetOutputLimits(-255, 255); // Ángulo (-255 a 255)
    myPIDX.SetOutputLimits(-255, 255); // Corredera (-255 a 255)
    myPIDV.SetOutputLimits(0, 255);    // Válvula (0 a 255)

    myPIDA.SetMode(AUTOMATIC);
    myPIDX.SetMode(AUTOMATIC);
    myPIDV.SetMode(AUTOMATIC);
    resetMotorX();
    resetMotorA();
}

void loop() {
    recibirDatos();            // Recibir datos de entrada
    leerSensores();            // Leer todos los sensores
    actualizarControlMotores(); // Controlar motores en base al modo (manual o PID)
    enviarDatos(); 
    leerSensorFlujo();// Enviar datos a través del puerto serial
}
void leerSensorFlujo() {
    unsigned long currentMillis = millis();
    if (currentMillis - lastUpdateTimeFlow >= updateIntervalFlowPID) {
        lastUpdateTimeFlow = currentMillis;
        Meter->tick(100); // Actualizar el flujo cada 100 ms (o el periodo que consideres adecuado)
        inputV = Meter->getCurrentFlowrate(); // Obtener el flujo actual
    }
  
}
// Funciones de inicialización
void iniciarMotores() {
    motorA.setSpeed(0);
    motorA.run(RELEASE);
    motorX.setSpeed(0);
    motorX.run(RELEASE);
    motorV.setSpeed(0);
    motorV.run(RELEASE);
}

void iniciarFlowMeter() {
  Meter = new FlowMeter(digitalPinToInterrupt(2), UncalibratedSensor, MeterISR, RISING);
 }

void MeterISR() {
    Meter->count();
}

// Lectura de sensores
void leerSensores() {
    leerDistancia();
    leerAngulo();
    // Aquí podrías añadir la lectura del medidor de flujo si lo deseas
}

void leerDistancia() {
 XState = digitalRead(outputA_X);
    XLimit_State = digitalRead(PinLimMinX);
    if (XState != XLastState) {
        if (digitalRead(outputB_X) != XState) {
            distance_counter++;
        } else {
            distance_counter--;
        }
    }
    XLastState = XState;
    if (XLimit_State) {
        distance_counter = 0;
    }
    inputX = distance_counter / stepsPerMM;
}

void leerAngulo() {
     AState = digitalRead(outputA_A);
    ALimit_State = digitalRead(pinLimMinA);
    if (AState != ALastState) {
        if (digitalRead(outputB_A) != AState) {
            angle_counter++;
        } else {
            angle_counter--;
        }
    }
    ALastState = AState;
    if (ALimit_State) {
        angle_counter = 0;
    }
     inputA = angle_counter / stepsPerDegree;

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
    // Limitar los valores en modo manual para la corredera y el ángulo
    if (inputX >= limMaxX && manualMotorX > 0) manualMotorX = 0; // Evitar sobrepasar el límite
    if (inputX <= limMinX && manualMotorX < 0) manualMotorX = 0;
    if (inputA >= limMaxA && manualMotorA > 0) manualMotorA = 0;
    if (inputA <= limMinA && manualMotorA < 0) manualMotorA = 0;

    motorA.setSpeed(abs(manualMotorA));
    motorX.setSpeed(abs(manualMotorX));
    motorV.setSpeed(abs(manualMotorV)); // La válvula solo va hacia adelante

    // Invertimos la dirección del motor angular
    motorA.run(manualMotorA > 0 ? BACKWARD : FORWARD); // Invertir aquí
    motorX.run(manualMotorX > 0 ? FORWARD : BACKWARD);
    motorV.run(FORWARD); // La válvula siempre corre hacia adelante
}

void controlar_motores_PID() {
    myPIDA.Compute();
    myPIDX.Compute();
    myPIDV.Compute();

    motorA.setSpeed(abs(EMA));
    motorX.setSpeed(abs(EMX));
    motorV.setSpeed(abs(EMV));

    // Invertimos la dirección del motor angular
    motorA.run(EMA > 0 ? BACKWARD : FORWARD); // Invertir aquí
    motorX.run(EMX > 0 ? FORWARD : BACKWARD);
    motorV.run(FORWARD); // La válvula siempre va en una dirección
}
// Enviar y recibir datos
void enviarDatos() {
    unsigned long currentMillis = millis();

    // Verificar si ha transcurrido el intervalo de tiempo
    if (currentMillis - previousMillis >= interval) {
        previousMillis = currentMillis; // Actualizar el tiempo previo

        // Preparar el documento JSON para enviar los datos
        StaticJsonDocument<512> doc;

        // Sensores
        JsonObject sensors = doc.createNestedObject("sensors");
        sensors["inX"] = inputX;  // Asegurarse de que inputX es un número válido
        sensors["inA"] = inputA;  // Asegurarse de que inputA es un número válido
        sensors["inV"] = inputV;  // Asegurarse de que inputV es un número válido
        sensors["flowVol"] = flowVolume;  // Asegurarse de que flowVolume es un número válido

        // Limites: Convertir a números (1 para true, 0 para false)
        sensors["limite_X"] = (inputX <= limMinX || inputX >= limMaxX) ? 1 : 0;
        sensors["limite_A"] = (inputA <= limMinA || inputA >= limMaxA) ? 1 : 0;

        // Estado de calibración: Convertir a números (1 para true, 0 para false)
        sensors["calibrando_X"] = calibrandoX ? 1 : 0;
        sensors["calibrando_A"] = calibrandoA ? 1 : 0;

        // Actuadores
        JsonObject actuators = doc.createNestedObject("actuators");
        actuators["energia_motor_corredera"] = manualMotorX;  // Asegurarse de que es un número
        actuators["energia_motor_angulo"] = manualMotorA;  // Asegurarse de que es un número
        actuators["energia_motor_valvula"] = manualMotorV;  // Asegurarse de que es un número
        actuators["manualMode"] = modoManual ? 1 : 0;  // Convertir el modo manual a número

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
        calibration["stepsPerMM"] = stepsPerMM;  // Asegurarse de que es un número
        calibration["stepsPerDegree"] = stepsPerDegree;  // Asegurarse de que es un número
        calibration["flowCalibFactor"] = flowCalibFactor;  // Asegurarse de que es un número

        // Serializar y enviar el JSON por el puerto serial
        serializeJson(doc, Serial);
        Serial.println();  // Asegurarse de que los datos sean enviados correctamente
    }
}


void recibirDatos() {
    if (Serial.available()) {
        String comando = Serial.readStringUntil('\n');
        procesarComando(comando);
    }
}

void procesarComando(String command) {
    StaticJsonDocument<512> doc;
    DeserializationError error = deserializeJson(doc, command);
    if (error) {
        Serial.println(F("Error parsing JSON command"));
        return;
    }
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

// Función de reset para la corredera (Motor X)
void resetMotorX() {
    calibrandoX = true; // Inicia la calibración de la corredera
    while (digitalRead(PinLimMinX) == LOW) {
        motorX.setSpeed(100);
        motorX.run(BACKWARD);
        enviarDatos();  // Enviar datos durante la calibración
        delay(10);
    }
    motorX.run(RELEASE);
    distance_counter = 0;
    calibrandoX = false; // Termina la calibración de la corredera
    enviarDatos();  // Enviar datos finales después de la calibración
}

// Función de reset para el ángulo (Motor A)
void resetMotorA() {
    calibrandoA = true; // Inicia la calibración del ángulo
    while (digitalRead(pinLimMinA) == LOW) {
        motorA.setSpeed(255);
        motorA.run(BACKWARD);
        enviarDatos();  // Enviar datos durante la calibración
        delay(10);
    }
    motorA.run(RELEASE);
    angle_counter = 0;
    calibrandoA = false; // Termina la calibración del ángulo
    enviarDatos();  // Enviar datos finales después de la calibración
}
