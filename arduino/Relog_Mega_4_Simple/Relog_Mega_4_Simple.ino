#include <AFMotor.h>
#include <FlowMeter.h>
#include <PID_v1.h>

// Motores
AF_DCMotor motorA(2); // Motor angular
AF_DCMotor motorX(3); // Motor lineal
AF_DCMotor motorV(1); // Bomba (solo hacia adelante)

// Calibración del sistema
float stepsPerMM = 1;
float stepsPerDegree = 1;
float flowCalibFactor = 1;
float flow = 0.0;
float volumen = 0.0;
float Vol_requerido = 0;
int resetVolumen = 0;
int modoManual = 0;
bool usarLectorVelocidad = true;  // true: usar sensor de flujo, false: controlar por tiempo
unsigned long tiempoInicioValvula = 0;  // Para control por tiempo

const int limMaxX = 400;  // Límite máximo en mm para corredera

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
bool resetX = true;
bool resetA = true;
unsigned long previousMillis = 0;
const long interval = 300; // Intervalo en milisegundos

// Control de PID
double A_Requerido = 0, inputA = 0, EMA = 0;
double kpA = 1, kiA = 1, kdA = 0.2;
PID myPIDA(&inputA, &EMA, &A_Requerido, kpA, kiA, kdA, DIRECT);

double X_Requerido = 0, inputX = 0, EMX = 0;
double kpX = 1, kiX = 1, kdX = 0.2;
PID myPIDX(&inputX, &EMX, &X_Requerido, kpX, kiX, kdX, DIRECT);

double EMV = 0;


// Flow Meter
FlowMeter *Meter;
const unsigned long period = 100; // Periodo de 1 segundo para la medición
unsigned long lastUpdateTimeFlow = 0;
const long updateIntervalFlowPID = 100; // Intervalo de actualización para el PID
// Declaración de constantes para los límites de energía
const int MIN_ENERGY = 80; // Energía mínima permitida
const int MAX_ENERGY = 255; // Energía máxima permitida



// Función para remapear energía
int remapEnergy(int energy) {
  if (abs(energy) < MIN_ENERGY && energy != 0) {
    return (energy > 0) ? MIN_ENERGY : -MIN_ENERGY;
  }
  return constrain(energy, -MAX_ENERGY, MAX_ENERGY);
}

// Declaración de la ISR antes de usarla
void MeterISR();

void setup() {
  // Preparar comunicación serial
  Serial.begin(115200);

  // Inicialización de pines
  pinMode(outputA_X, INPUT);
  pinMode(outputB_X, INPUT);
  pinMode(PinLimMinX, INPUT);

  pinMode(outputA_A, INPUT);
  pinMode(outputB_A, INPUT);
  pinMode(pinLimMinA, INPUT);

  // Inicialización de motores y PID
  iniciarMotores();
  iniciarFlowMeter();

  // Establecer límites para PID
  myPIDA.SetOutputLimits(-255, 255); // Ángulo (-255 a 255)
  myPIDX.SetOutputLimits(-255, 255); // Corredera (-255 a 255)

  myPIDA.SetMode(AUTOMATIC);
  myPIDX.SetMode(AUTOMATIC);


}

void loop() {
  recibirDatos();             // Recibir datos de entrada
  leerSensores();             // Leer todos los sensores
  leerSensorFlujo();          // Actualizar flujo antes de enviar datos
  actualizarControlMotores(); // Controlar motores en base al modo (manual o PID)
  enviarDatos();              // Enviar datos a través del puerto serial
}

void leerSensorFlujo() {
  if (!usarLectorVelocidad) return;

  unsigned long currentMillis = millis();
  if (currentMillis - lastUpdateTimeFlow >= updateIntervalFlowPID) {
    unsigned long deltaMillis = currentMillis - lastUpdateTimeFlow;
    lastUpdateTimeFlow = currentMillis;
    Meter->tick(deltaMillis); // Actualizar el flujo con el tiempo transcurrido

    flow = Meter->getCurrentFlowrate(); // Obtener el flujo actual
    volumen = Meter->getTotalVolume(); // Actualizar volumen total
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
  // Obtener una nueva instancia de FlowMeter para un sensor no calibrado en el pin 2
  Meter = new FlowMeter(digitalPinToInterrupt(2), UncalibratedSensor, MeterISR, RISING);
}

void MeterISR() {
  // Permitir que el FlowMeter cuente los pulsos
  Meter->count();
}

// Lectura de sensores
void leerSensores() {
  // Leer estados de los interruptores de límite mínimo
  XLimit_State = digitalRead(PinLimMinX);
  ALimit_State = digitalRead(pinLimMinA);

  leerDistancia();
  leerAngulo();
}

void leerDistancia() {
  XState = digitalRead(outputA_X);

  if (XState != XLastState) {
    if (digitalRead(outputB_X) != XState) {
      distance_counter++;
    } else {
      if (distance_counter > 0) { // Evitar que sea menor que 1
        distance_counter--;
      } else {
        distance_counter = 0; // Mantener en 1
      }
    }
  }

  XLastState = XState;

  if (XLimit_State == HIGH) {
    distance_counter = 0; // Establecer en 1 en lugar de cero
  }

  // Proteger contra división por cero
  if (stepsPerMM != 0) {
    inputX = distance_counter / stepsPerMM;
  } else {
    inputX = distance_counter;
  }
}



void leerAngulo() {
  AState = digitalRead(outputA_A);

  if (AState != ALastState) {
    if (digitalRead(outputB_A) != AState) {
      angle_counter++;
    } else {
      if (angle_counter > 0) { // Evitar que sea menor que 1
        angle_counter--;
      } else {
        angle_counter = 0; // Mantener en 1
      }
    }
  }

  ALastState = AState;

  if (ALimit_State == HIGH) {
    angle_counter = 0; // Establecer en 1 en lugar de cero
  }

  // Proteger contra división por cero
  if (stepsPerDegree != 0 && angle_counter != 0 ) {
    inputA = angle_counter / stepsPerDegree;
  } else {
    inputA = angle_counter;
  }

}

// Control de los motores
void actualizarControlMotores() {
  if (resetX || resetA) {
    controlar_motores_reset();
  } else if (!modoManual) {
    controlar_motores_PID();
  } else {
    controlar_motores_manual();
  }
}


// Control manual de motores actualizado
void controlar_motores_manual() {
  // Leer estados de los interruptores de límite mínimo
  XLimit_State = digitalRead(PinLimMinX);
  ALimit_State = digitalRead(pinLimMinA);

  // Ajustar los outputs del PID para respetar los límites
  double adjusted_EMX = EMX;
  double adjusted_EMA = EMA;

  // Limitar movimiento del Motor X (Corredera)
  if (XLimit_State == HIGH && EMX < 0) {
    adjusted_EMX = 0; // No permitir moverse más hacia el límite mínimo
    distance_counter = 0;
  }
  if (inputX >= limMaxX && EMX > 0) {
    adjusted_EMX = 0; // No permitir moverse más hacia el límite máximo
  }

  // Limitar movimiento del Motor A (Ángulo)
  if (ALimit_State == HIGH && EMA < 0) {
    adjusted_EMA = 0; // No permitir moverse más hacia el límite mínimo
    angle_counter = 0;
  }
  if (inputA >= limMaxA && EMA > 0) {
    adjusted_EMA = 0; // No permitir moverse más hacia el límite máximo
  }

  // Aplicar mapeo de energía
  adjusted_EMX = remapEnergy(adjusted_EMX);
  adjusted_EMA = remapEnergy(adjusted_EMA);
  EMV = remapEnergy(EMV);

  // Configurar las velocidades de los motores
  motorA.setSpeed(abs(adjusted_EMA));
  motorX.setSpeed(abs(adjusted_EMX));
  motorV.setSpeed(abs(EMV));

  // Configurar la dirección de los motores
  motorA.run(adjusted_EMA > 0 ? FORWARD : BACKWARD);
  motorX.run(adjusted_EMX > 0 ? FORWARD : BACKWARD);
  motorV.run(FORWARD); // La válvula siempre va en una dirección
}

// Control PID de motores actualizado
void controlar_motores_PID() {
  // Calcular los outputs del PID
  myPIDA.Compute();
  myPIDX.Compute();

  // Leer estados de los interruptores de límite mínimo
  XLimit_State = digitalRead(PinLimMinX);
  ALimit_State = digitalRead(pinLimMinA);

  // Ajustar los outputs del PID para respetar los límites
  double adjusted_EMX = EMX;
  double adjusted_EMA = EMA;

  // Limitar movimiento del Motor X (Corredera)
  if (XLimit_State == HIGH && EMX < 0) {
    adjusted_EMX = 0; // No permitir moverse más hacia el límite mínimo
  }
  if (inputX >= limMaxX && EMX > 0) {
    adjusted_EMX = 0; // No permitir moverse más hacia el límite máximo
  }

  // Limitar movimiento del Motor A (Ángulo)
  if (ALimit_State == HIGH && EMA < 0) {
    adjusted_EMA = 0; // No permitir moverse más hacia el límite mínimo
  }
  if (inputA >= limMaxA && EMA > 0) {
    adjusted_EMA = 0; // No permitir moverse más hacia el límite máximo
  }

  // Aplicar mapeo de energía
  adjusted_EMX = remapEnergy(adjusted_EMX);
  adjusted_EMA = remapEnergy(adjusted_EMA);
  EMV = remapEnergy(EMV);

  // Controlar el volumen usando el sensor o solo por tiempo
  if (usarLectorVelocidad) {
    if (volumen < Vol_requerido) {
      motorV.setSpeed(255);
      motorV.run(FORWARD);
    } else {
      motorV.setSpeed(0);
      motorV.run(RELEASE);
    }
  } else {
    if (Vol_requerido > 0) {
      if (tiempoInicioValvula == 0) tiempoInicioValvula = millis();
      if (millis() - tiempoInicioValvula < (unsigned long)(Vol_requerido * 1000)) {
        motorV.setSpeed(255);
        motorV.run(FORWARD);
      } else {
        motorV.setSpeed(0);
        motorV.run(RELEASE);
        Vol_requerido = 0;
        tiempoInicioValvula = 0;
      }
    } else {
      motorV.setSpeed(0);
      motorV.run(RELEASE);
    }
  }

  // Configurar las velocidades de los motores
  motorA.setSpeed(abs(adjusted_EMA));
  motorX.setSpeed(abs(adjusted_EMX));

  // Configurar la dirección de los motores
  motorA.run(adjusted_EMA > 0 ? FORWARD : BACKWARD);
  motorX.run(adjusted_EMX > 0 ? FORWARD : BACKWARD);
}


void enviarDatos() {
  unsigned long currentMillis = millis();

  // Verificar si ha transcurrido el intervalo de tiempo
  if (currentMillis - previousMillis >= interval) {
    previousMillis = currentMillis; // Actualizar el tiempo previo
    XLimit_State = digitalRead(PinLimMinX);
    ALimit_State = digitalRead(pinLimMinA);
    // Preparar la cadena de datos separados por comas
    String dataString = String('<') +
                        String(inputX, 2) + "," +
                        String(inputA, 2) + "," +
                        String(volumen, 2) + "," +
                        String(flow, 2) + "," +
                        String(XLimit_State, 2) + "," +
                        String(ALimit_State, 2) + "," +
                        String(resetX ? 1 : 0) + "," +
                        String(resetA ? 1 : 0) + "," +
                        String(EMX, 2) + "," +
                        String(EMA, 2) + "," +
                        String(EMV, 2) + "," +
                        String(modoManual, 2) + "," +
                        String(kpX, 2) + "," +
                        String(kiX, 2) + "," +
                        String(kdX, 2) + "," +
                        String(kpA, 2) + "," +
                        String(kiA, 2) + "," +
                        String(kdA, 2) + "," +
                        String(stepsPerMM, 2) + "," +
                        String(stepsPerDegree, 2) + "," +
                        String(flowCalibFactor, 2) +
                        String('>');

    // Enviar la cadena por el puerto serial
    Serial.println(dataString);
  }
}

void recibirDatos() {
  if (Serial.available()) {
    String comando = Serial.readStringUntil('\n');
    procesarComando(comando);
  }
}

void procesarComando(String command) {
  // Separar la cadena por comas
  int index = 0;
  String values[20];  // Asegúrate de tener espacio suficiente para todos los datos
  while (command.indexOf(',') != -1 && index < 19) {
    values[index++] = command.substring(0, command.indexOf(','));
    command = command.substring(command.indexOf(',') + 1);
  }
  values[index] = command;  // El último valor

  // Verificar que tenemos exactamente 20 valores
  if (index != 19) {
    Serial.println("Error: Datos incompletos o excesivos recibidos.");
    return;
  }

  // Asignar valores a las variables correspondientes
  modoManual = values[0].toInt() ;  // Primer valor es modoManual (1 o 0)
  EMA = values[1].toInt();     // Motor angular
  EMX = values[2].toInt();     // Motor lineal
  EMV = values[3].toInt();     // Bomba
  X_Requerido = values[4].toFloat();    // Setpoint corredera
  A_Requerido = values[5].toFloat();    // Setpoint ángulo
  Vol_requerido =  values[6].toFloat(); // Setpoint flujo

  kpX = values[7].toFloat();            // kp PID corredera
  kiX = values[8].toFloat();            // ki PID corredera
  kdX = values[9].toFloat();            // kd PID corredera
  kpA = values[10].toFloat();           // kp PID ángulo
  kiA = values[11].toFloat();           // ki PID ángulo
  kdA = values[12].toFloat();           // kd PID ángulo
  resetVolumen = values[13].toInt();
  // Procesar reset de motores
  bool resetMotorXFlag = values[14].toInt() == 1;  // Si el valor es 1, hacer reset del motor X
  bool resetMotorAFlag = values[15].toInt() == 1;  // Si el valor es 1, hacer reset del motor A


  if (resetMotorXFlag) resetX = true;
  if (resetMotorAFlag) resetA = true;

  // Procesar valores de calibración
  float newStepsPerMM = values[16].toFloat();      // Calibración en pasos por milímetro
  float newStepsPerDegree = values[17].toFloat();  // Calibración en pasos por grado
  usarLectorVelocidad = values[18].toInt() == 1;

  // Asegurarse de que no sean cero para evitar divisiones por cero
  if (newStepsPerMM != 0) stepsPerMM = newStepsPerMM;
  if (newStepsPerDegree != 0) stepsPerDegree = newStepsPerDegree;

  // Aplicar los nuevos valores de PID
  myPIDX.SetTunings(kpX, kiX, kdX);
  myPIDA.SetTunings(kpA, kiA, kdA);

  if (resetVolumen == 1) {
    resetVolumen = 0; // Restablecer la bandera para evitar múltiples reinicios

    // Reiniciar el volumen acumulado
    Meter->reset();
    volumen = 0.0; // Reiniciar el volumen en el código
    tiempoInicioValvula = 0;
  }


}
void controlar_motores_reset() {
  // Asegurarse de que estamos en modo manual
  modoManual = 1;

  // Si se está reseteando el motor X
  if (resetX) {
    if (XLimit_State == LOW) {
      // Ajustar EMX para mover hacia atrás
      EMX = -200;  // Ajusta el valor según sea necesario
    } else {
      // Límite alcanzado
      EMX = 0;
      resetX = false;
      distance_counter = 0;
      motorX.run(RELEASE);  // Asegurar que el motor esté detenido
    }
  }

  // Si se está reseteando el motor A
  if (resetA) {
    if (ALimit_State == LOW) {
      // Ajustar EMA para mover hacia atrás
      EMA = -200;  // Ajusta el valor según sea necesario
    } else {
      // Límite alcanzado
      EMA = 0;
      resetA = false;
      angle_counter = 0;
      motorA.run(RELEASE);  // Asegurar que el motor esté detenido
    }
  }

  // Ahora, llamar a la función de control manual para aplicar EMX y EMA
  controlar_motores_manual();
}
