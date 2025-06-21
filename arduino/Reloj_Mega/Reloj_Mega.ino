#include <Wire.h>
#include <AFMotor.h>
#include <FlowMeter.h>
#include <PID_v1.h>
#include <Servo.h>

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
int compass_debug = 0;

#define Task_t 10
int dt = 0;
unsigned long t;

// Pines de los motores
AF_DCMotor MotorA(2);
AF_DCMotor MotorX(3);
AF_DCMotor MotorV(1);

Servo servoH;
Servo servoV;

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
const int PinLimMinA = 32;
int angle_counter = 0;
int AState = 0;
int ALastState = 0;
int ALimit_State = 0;

const int PinLimMinV = 13;
unsigned long lastUpdateTimeX = 0;
float LimMinVState = 0;

// Control de los tiempos
unsigned long lastUpdateTimeAngle = 0;
const long updateIntervalAnglePID = 300;
const long updateIntervalPID_X = 300;
unsigned long lastUpdateTimeDatos = 0;
const long updateIntervalDatos = 300;
unsigned long lastUpdateTimeFlow = 0;
const long updateIntervalFlowPID = 100;

FlowMeter *Meter;
const unsigned long period = 100;

float A = 0;
double A_Requerido, inputA, EMA;
double kpA = 1, kiA = 1, kdA = 0.2;
PID myPIDA(&inputA, &EMA, &A_Requerido, kpA, kiA, kdA, DIRECT);

float X = 0;
double X_Requerido, inputX, EMX;
double kpX = 1, kiX = 1, kdX = 0.2;
PID myPIDX(&inputX, &EMX, &X_Requerido, kpX, kiX, kdX, DIRECT);

float VEL = 0;
double Vel_Requerida, inputV, EMV;
double kpV = 15, kiV = 0, kdV = 0;
PID myPIDV(&inputV, &EMV, &Vel_Requerida, kpV, kiV, kdV, DIRECT);

// Variables para el modo manual
bool modoManual = false;
int manualMotorA = 0;
int manualMotorX = 0;
int manualMotorV = 0;

void setup() {
    Serial.begin(115200);
    Wire.begin();
    compass_x_offset = 122.17;
    compass_y_offset = 230.08;
    compass_z_offset = 389.85;
    compass_x_gainError = 1.12;
    compass_y_gainError = 1.13;
    compass_z_gainError = 1.03;
    compass_init(2);

    MotorA.setSpeed(255);
    MotorA.run(RELEASE);

    MotorX.setSpeed(255);
    MotorX.run(RELEASE);

    MotorV.setSpeed(255);
    MotorV.run(RELEASE);

    Meter = new FlowMeter(digitalPinToInterrupt(2), UncalibratedSensor, MeterISR, RISING);
    pinMode(PinLimMinV, INPUT_PULLUP);

    A_Requerido = 0;
    inputA = 0;
    myPIDA.SetOutputLimits(-255, 255);
    myPIDA.SetMode(AUTOMATIC);

    X_Requerido = 0;
    inputX = 0;
    myPIDX.SetOutputLimits(-255, 255);
    myPIDX.SetMode(AUTOMATIC);

    Vel_Requerida = 0;
    inputV = 0;
    myPIDV.SetOutputLimits(-255, 255);
    myPIDV.SetMode(AUTOMATIC);

    servoH.attach(9);
    servoV.attach(10);
    servoH.write(0);
    servoV.write(0);

    pinMode(PinLimMinX, INPUT);
    pinMode(PinLimMinA, INPUT);
    pinMode(outputA_A, INPUT);
    pinMode(outputB_A, INPUT);
    pinMode(outputA_X, INPUT);
    pinMode(outputB_X, INPUT);

    resetServos();
    resetMotorX();
    resetMotorA();
    compass_offset_calibration(); // Calibración al inicio
}

void loop() {
    recibirDatos();           // Recibir los datos de entrada
    get_distance();           // Leer la distancia para el motor X
    get_horizontal_angle();   // Leer el ángulo horizontal para el motor A
    leerSensorFlujo_PID();     // Leer el flujo y actualizar el PID para el motor V
    leerSensorLongitud_PID();  // Leer la longitud y actualizar el PID para el motor X
    leerSensorAngulo_PID();    // Leer el ángulo y actualizar el PID para el motor A

    if (!modoManual) {
        controlar_motores_PID(); // Llamar a la función de control automático para los motores
    } else {
        controlarMotoresManual(); // Control manual si está activado
    }

    enviarDatos(); // Enviar los datos actualizados
}

void MeterISR() {
    Meter->count();
}

void get_distance() {
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
}

void leerSensorLongitud_PID() {
    unsigned long currentMillis = millis();
    if (currentMillis - lastUpdateTimeX >= updateIntervalPID_X) {
        lastUpdateTimeX = currentMillis;
        inputX = distance_counter;
        myPIDX.Compute();
    }
}

void get_horizontal_angle() {
    AState = digitalRead(outputA_A);
    ALimit_State = digitalRead(PinLimMinA);
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
}

void leerSensorAngulo_PID() {
    unsigned long currentMillis = millis();
    if (currentMillis - lastUpdateTimeAngle >= updateIntervalAnglePID) {
        lastUpdateTimeAngle = currentMillis;
        inputA = angle_counter;
        myPIDA.Compute();
    }
}

void leerSensorFlujo_PID() {
    unsigned long currentMillis = millis();
    if (currentMillis - lastUpdateTimeFlow >= updateIntervalFlowPID) {
        lastUpdateTimeFlow = currentMillis;
        Meter->tick(period);
        inputV = Meter->getCurrentFlowrate();
    }
    myPIDV.Compute();
    MoverMotorV(mapOutput(EMV), FORWARD);
}

void enviarDatos() {
    unsigned long currentMillis = millis();
    if (currentMillis - lastUpdateTimeDatos >= updateIntervalDatos) {
        lastUpdateTimeDatos = currentMillis;
        int anguloHActual = servoH.read();
        int anguloVActual = servoV.read();
        float inputAActual = inputA;
        float inputXActual = inputX;
        float inputVActual = inputV;
        double ARequerido = A_Requerido;
        double XRequerido = X_Requerido;
        double VelRequerida = Vel_Requerida;
        double kpA = myPIDA.GetKp(), kiA = myPIDA.GetKi(), kdA = myPIDA.GetKd();
        double kpX = myPIDX.GetKp(), kiX = myPIDX.GetKi(), kdX = myPIDX.GetKd();
        double kpV = myPIDV.GetKp(), kiV = myPIDV.GetKi(), kdV = myPIDV.GetKd();
        int limMinVState = digitalRead(PinLimMinV);

        String datos = String("V") + "," +
                       String(anguloHActual) + "," +
                       String(anguloVActual) + "," +
                       String(inputVActual) + "," +
                       String(inputAActual) + "," +
                       String(inputXActual) + "," +
                       String(VelRequerida) + "," +
                       String(ARequerido) + "," +
                       String(XRequerido) + "," +
                       String(kpV) + "," + String(kiV) + "," + String(kdV) + "," +
                       String(kpA) + "," + String(kiA) + "," + String(kdA) + "," +
                       String(kpX) + "," + String(kiX) + "," + String(kdX) + "," +
                       String(limMinVState) + "," +
                       String(ALimit_State) + "," +
                       String(XLimit_State);

        Serial.println(datos);
    }
}

void recibirDatos() {
    if (Serial.available()) {
        String comando = Serial.readStringUntil('\n');
        procesarComando(comando);
    }
}

void procesarComando(String comando) {
    int numParams = 19; // Ajustamos el número de parámetros
    String params[numParams];
    for (int i = 0; i < numParams; i++) {
        int index = comando.indexOf(',');
        if (index == -1) index = comando.length();
        params[i] = comando.substring(0, index);
        comando = comando.substring(index + 1);
    }
    int anguloH = params[0].toInt();
    int anguloV = params[1].toInt();
    servoH.write(anguloH);
    servoV.write(anguloV);
    Vel_Requerida = params[2].toFloat();
    A_Requerido = params[3].toFloat();
    X_Requerido = params[4].toFloat();
    myPIDV.SetTunings(params[5].toFloat(), params[6].toFloat(), params[7].toFloat());
    myPIDA.SetTunings(params[8].toFloat(), params[9].toFloat(), params[10].toFloat());
    myPIDX.SetTunings(params[11].toFloat(), params[12].toFloat(), params[13].toFloat());

    // Verificamos si hay un valor de calibración
    int calibrar = params[14].toInt();
    if (calibrar == 1) {
        compass_offset_calibration();
        Serial.println("Calibracion Completa");
    }

    // Verificamos si hay un valor para el modo manual
    modoManual = params[15].toInt() == 1;
    if (modoManual) {
        manualMotorA = params[16].toInt();
        manualMotorX = params[17].toInt();
        manualMotorV = params[18].toInt();
    }
}

int mapOutput(double output) {
    if (output > 0) {
        return map(output, 0, 255, 70, 255);
    } else if (output < 0) {
        return map(output, -255, 0, -255, -70);
    }
    return 0;
}

void MoverMotorA(int scaledOutput, int direction) {
    if (scaledOutput > 0) {
        if (digitalRead(PinLimMinA) == LOW) { // Verificar si no se ha alcanzado el límite
            MotorA.setSpeed(scaledOutput);   // Establecer la velocidad según el PID
            MotorA.run(direction);           // Mover en la dirección especificada
        } else {
            MotorA.setSpeed(0);              // Detener el motor si se alcanza el límite
            MotorA.run(RELEASE);
        }
    } else if (scaledOutput < 0) {
        if (inputA != 0) {                   // Verificar que el inputA sea válido
            MotorA.setSpeed(abs(scaledOutput)); // Establecer la velocidad con dirección opuesta
            MotorA.run(direction == FORWARD ? BACKWARD : FORWARD); // Invertir dirección
        } else {
            MotorA.setSpeed(0);              // Detener el motor si no hay input válido
            MotorA.run(RELEASE);
        }
    } else {
        MotorA.setSpeed(0);                  // Detener el motor si scaledOutput es 0
        MotorA.run(RELEASE);
    }
}

void MoverMotorX(int scaledOutput, int direction) {
    if (scaledOutput > 0) {
        if (digitalRead(PinLimMinX) == LOW) { // Verificar si no se ha alcanzado el límite
            MotorX.setSpeed(scaledOutput);   // Establecer la velocidad según el PID
            MotorX.run(direction);           // Mover en la dirección especificada
        } else {
            MotorX.setSpeed(0);              // Detener el motor si se alcanza el límite
            MotorX.run(RELEASE);
        }
    } else if (scaledOutput < 0) {
        if (inputX != 0) {                   // Verificar que el inputX sea válido
            MotorX.setSpeed(abs(scaledOutput)); // Establecer la velocidad con dirección opuesta
            MotorX.run(direction == FORWARD ? BACKWARD : FORWARD); // Invertir dirección
        } else {
            MotorX.setSpeed(0);              // Detener el motor si no hay input válido
            MotorX.run(RELEASE);
        }
    } else {
        MotorX.setSpeed(0);                  // Detener el motor si scaledOutput es 0
        MotorX.run(RELEASE);
    }
}

void MoverMotorV(int scaledOutput, int direction) {
    if (scaledOutput > 0) {
        if (digitalRead(PinLimMinV) == LOW) { // Verificar si no se ha alcanzado el límite
            MotorV.setSpeed(scaledOutput);   // Establecer la velocidad según el PID
            MotorV.run(direction);           // Mover en la dirección especificada
            delay(3);                        // Pequeño retraso para estabilidad
        }
    } else if (scaledOutput < 0) {
        if (inputV != 0) {                   // Verificar que el inputV sea válido
            MotorV.setSpeed(abs(scaledOutput)); // Establecer la velocidad con dirección opuesta
            MotorV.run(direction == FORWARD ? BACKWARD : FORWARD); // Invertir dirección
            delay(3);                        // Pequeño retraso para estabilidad
        }
    } else {
        MotorV.setSpeed(0);                  // Detener el motor si scaledOutput es 0
        MotorV.run(RELEASE);
        delay(3);                            // Pequeño retraso para estabilidad
    }
}

void resetServos() {
    servoH.write(0);
    servoV.write(0);
}

void resetMotorX() {
    Serial.println("Reseteando Motor X");
    while (digitalRead(PinLimMinX) == LOW) {
        Serial.print("Estado PinLimMinX: ");
        Serial.println(digitalRead(PinLimMinX));
        MotorX.setSpeed(100);
        MotorX.run(BACKWARD);

        // Leer sensores y enviar datos
        get_distance();        // Actualiza el contador de distancia
        leerSensorLongitud_PID(); // Actualiza el PID si es necesario
        enviarDatos();            // Envía los datos actualizados
        recibirDatos();           // Procesar entradas si es necesario

        delay(10);
    }
    MotorX.run(RELEASE);
    distance_counter = 0;
}

void resetMotorA() {
    Serial.println("Reseteando Motor A");
    while (digitalRead(PinLimMinA) == LOW) {
        Serial.print("Estado PinLimMinA: ");
        Serial.println(digitalRead(PinLimMinA));
        MotorA.setSpeed(255);
        MotorA.run(BACKWARD);

        // Leer sensores y enviar datos
        get_horizontal_angle(); // Actualiza el contador de ángulos
        leerSensorAngulo_PID(); // Actualiza el PID si es necesario
        enviarDatos();          // Envía los datos actualizados
        recibirDatos();         // Procesar entradas si es necesario

        delay(10);
    }
    MotorA.run(RELEASE);
    angle_counter = 0;
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

void compass_offset_calibration() {
    Serial.println("Calibrando el Magnetómetro ....... Offset");

    bool llendo = true; // true para FORWARD (llendo), false para BACKWARD (viniendo)
    int vueltasCompletadas = 0;
    const int maxVueltas = 2; // Una rotación completa hacia cada lado
    const int pasosInicialesAntesDeLimite = 500; // Pasos iniciales antes de verificar el límite

    int pasosDesdeInicio = 0; // Contador de pasos desde el inicio de la dirección

    // Valores máximos y mínimos durante la calibración
    float x_max = -4000, y_max = -4000, z_max = -4000;
    float x_min = 4000, y_min = 4000, z_min = 4000;

    while (vueltasCompletadas < maxVueltas) {
        get_horizontal_angle(); // Actualizar el contador de ángulos
        pasosDesdeInicio++; // Incrementar contador de pasos desde inicio

        // Mover el motor en la dirección actual usando la función MoverMotorA
        if (llendo) {
            MotorA.setSpeed(255);
            MotorA.run(FORWARD);
        } else {
            MotorA.setSpeed(255);
            MotorA.run(BACKWARD);
        }

        // Verificar si se han dado suficientes pasos para permitir el uso del límite
        if (pasosDesdeInicio > pasosInicialesAntesDeLimite) {
            // Verificar si se ha alcanzado el límite
            if (digitalRead(PinLimMinA) == HIGH) {
                llendo = !llendo; // Cambiar de dirección
                angle_counter = 0; // Reiniciar el contador de pasos al cambiar de dirección
                pasosDesdeInicio = 0; // Reiniciar contador de pasos desde el inicio
                vueltasCompletadas++;
            }
        }

        compass_read_XYZdata();
        compass_x_scalled = (float)compass_x * compass_gain_fact * compass_x_gainError;
        compass_y_scalled = (float)compass_y * compass_gain_fact * compass_y_gainError;
        compass_z_scalled = (float)compass_z * compass_gain_fact * compass_z_gainError;

        // Actualización de valores máximos y mínimos
        x_max = max(x_max, compass_x_scalled);
        y_max = max(y_max, compass_y_scalled);
        z_max = max(z_max, compass_z_scalled);
        x_min = min(x_min, compass_x_scalled);
        y_min = min(y_min, compass_y_scalled);
        z_min = min(z_min, compass_z_scalled);

        // Leer otros sensores si es necesario
        get_distance();        // Actualizar contador de distancia
        leerSensorFlujo_PID(); // Actualizar el PID del flujo si aplica

        // Enviar datos
        enviarDatos();
        recibirDatos();        // Procesar entradas si es necesario

        delay(10);
    }

    // Apagar el motor después de la calibración
    MotorA.run(RELEASE);
    Serial.println("Calibración completada");

    // Cálculo de los offsets
    compass_x_offset = ((x_max - x_min) / 2) - x_max;
    compass_y_offset = ((y_max - y_min) / 2) - y_max;
    compass_z_offset = ((z_max - z_min) / 2) - z_max;

    // Imprimir los resultados de la calibración
    Serial.print("Offset x  = ");
    Serial.print(compass_x_offset);
    Serial.println(" mG");
    Serial.print("Offset y  = ");
    Serial.print(compass_y_offset);
    Serial.println(" mG");
    Serial.print("Offset z  = ");
    Serial.print(compass_z_offset);
    Serial.println(" mG");

    // Restablecer el motor A al final de la calibración
    resetMotorA();
}

void controlarMotoresManual() {
    MotorA.setSpeed(abs(manualMotorA));
    MotorA.run(manualMotorA > 0 ? FORWARD : BACKWARD);

    MotorX.setSpeed(abs(manualMotorX));
    MotorX.run(manualMotorX > 0 ? FORWARD : BACKWARD);

    MotorV.setSpeed(abs(manualMotorV));
    MotorV.run(manualMotorV > 0 ? FORWARD : BACKWARD);
}

void controlar_motores_PID() {
    // Control del motor A
    int outputA = mapOutput(EMA); // Mapea el valor de salida del PID para A
    if (outputA > 0) {
        MoverMotorA(outputA, FORWARD);
    } else if (outputA < 0) {
        MoverMotorA(abs(outputA), BACKWARD);
    } else {
        MotorA.run(RELEASE);
    }

    // Control del motor X
    int outputX = mapOutput(EMX); // Mapea el valor de salida del PID para X
    if (outputX > 0) {
        MoverMotorX(outputX, FORWARD);
    } else if (outputX < 0) {
        MoverMotorX(abs(outputX), BACKWARD);
    } else {
        MotorX.run(RELEASE);
    }

    // Control del motor V
    int outputV = mapOutput(EMV); // Mapea el valor de salida del PID para V
    if (outputV > 0) {
        MoverMotorV(outputV, FORWARD);
    } else if (outputV < 0) {
        MoverMotorV(abs(outputV), BACKWARD);
    } else {
        MotorV.run(RELEASE);
    }
}

void compass_init(int gain) {
    byte gain_reg, mode_reg;
    Wire.beginTransmission(compass_address);
    Wire.write(0x01);
    if (gain == 0) {
        gain_reg = 0b00000000;
        compass_gain_fact = 0.73;
    } else if (gain == 1) {
        gain_reg = 0b00100000;
        compass_gain_fact = 0.92;
    } else if (gain == 2) {
        gain_reg = 0b01000000;
        compass_gain_fact = 1.22;
    } else if (gain == 3) {
        gain_reg = 0b01100000;
        compass_gain_fact = 1.52;
    } else if (gain == 4) {
        gain_reg = 0b10000000;
        compass_gain_fact = 2.27;
    } else if (gain == 5) {
        gain_reg = 0b10100000;
        compass_gain_fact = 2.56;
    } else if (gain == 6) {
        gain_reg = 0b11000000;
        compass_gain_fact = 3.03;
    } else if (gain == 7) {
        gain_reg = 0b11100000;
        compass_gain_fact = 4.35;
    }
    Wire.write(gain_reg);
    Wire.write(0b00000011);
    Wire.endTransmission();
    Serial.print("Gain updated to  = ");
    Serial.print(compass_gain_fact);
    Serial.println(" mG/bit");
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
