#include <Arduino.h>
#include <FlowMeter.h>
#include <Servo.h>
#include <PID_v1.h>

// Configuración de pines y parámetros
#define flowMeterPin 2  // Pin de interrupción para el sensor de flujo
#define period 300      // Periodo de actualización de la medida en ms

// Instancia de FlowMeter
FlowMeter *Meter;

// Variables para el PID y los servos
Servo servoValvula;
Servo servoHorizontal;
Servo servoVertical;
double Setpoint, Input, Output;
double flowSetpoint = 5.0; // Punto de ajuste inicial para el flujo
double Kp = -2.0, Ki = 5.0, Kd = 1.0;
PID myPID(&Input, &Output, &Setpoint, Kp, Ki, Kd, DIRECT);
int angleHorizontal = 90; // Ángulo inicial para el servo horizontal
int angleVertical = 90;   // Ángulo inicial para el servo vertical
int angleValve = 90;      // Ángulo inicial para el servo de la válvula
bool useUserValue = false; // Indicador para usar valor del usuario o PID

unsigned long lastUpdateTime = 0; // Variable para controlar el envío de datos

// Función de interrupción para contar el flujo
void MeterISR() {
    // let our flow meter count the pulses
    Meter->count();
}

void setup() {
    Serial.begin(115200);
    pinMode(flowMeterPin, INPUT_PULLUP);
    Meter = new FlowMeter(digitalPinToInterrupt(2), UncalibratedSensor, MeterISR, RISING);
    // Inicializar los servos y el PID
    servoValvula.attach(8);
    servoHorizontal.attach(6);
    servoVertical.attach(5);
    
    Setpoint = flowSetpoint;
    myPID.SetMode(AUTOMATIC);
    myPID.SetOutputLimits(0, 180);

    // Establecer ángulos iniciales de los servos
    servoHorizontal.write(angleHorizontal);
    servoVertical.write(angleVertical);
}

void loop() {
    // Procesar la comunicación serial
    if (Serial.available() > 0) {
        String receivedData = Serial.readStringUntil('\n');
        int values[8];
        int startIndex = 0, endIndex = 0, i = 0;

        while (i < 8 && (endIndex = receivedData.indexOf(',', startIndex)) != -1) {
            values[i++] = receivedData.substring(startIndex, endIndex).toInt();
            startIndex = endIndex + 1;
        }
        if (i < 8) {
            values[i] = receivedData.substring(startIndex).toInt();
        }

        // Asignación de valores recibidos a las variables
        angleHorizontal = values[0];
        angleVertical = values[1];
        flowSetpoint = values[2];
        Kp = values[4];
        Ki = values[5];
        Kd = values[6];
        angleValve = values[7];
        useUserValue = values[3]; // 0 para usar el PID, 1 para valor del usuario

        // Actualizar PID y ángulos
        myPID.SetTunings(Kp, Ki, Kd);
        Setpoint = flowSetpoint;
        servoHorizontal.write(angleHorizontal);
        servoVertical.write(angleVertical);
    }

    // Enviar datos cada `period` milisegundos
    unsigned long currentTime = millis();
    if (currentTime - lastUpdateTime >= period) {
        // Procesar las pulsaciones contadas
        Meter->tick(period);
        // Actualizar el PID con la tasa de flujo actual
        Input = Meter->getCurrentFlowrate();
        myPID.Compute();

        // Usar el valor del usuario o el valor del PID para el servo de la válvula
        if (useUserValue) {
            servoValvula.write(angleValve);
        } else {
            servoValvula.write((int)Output);
        }

        // Mostrar datos en formato CSV
        Serial.print(Setpoint);
        Serial.print(",");
        Serial.print(Input);
        Serial.print(",");
        Serial.print(Output);
        Serial.print(",");
        Serial.print(Kp);
        Serial.print(",");
        Serial.print(Ki);
        Serial.print(",");
        Serial.print(Kd);
        Serial.print(",");
        Serial.print(angleHorizontal);
        Serial.print(",");
        Serial.print(angleVertical);
        Serial.print(",");
        Serial.print(angleValve);
        Serial.print(",");
        Serial.print(useUserValue); // Añadido el valor useUserValue al final
        Serial.println();

        lastUpdateTime = currentTime;
    }
}
