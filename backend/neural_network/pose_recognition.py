"""
Clasificador local de postura: envuelve el modelo TFLite entrenado y
validado en shpd-edge-vision (ver
shpd-edge-vision/model/Keypoint_model_training.ipynb), que clasifica los
landmarks de MediaPipe Pose de UN frame en una de 12 posturas problemáticas.

Adaptado de shpd-edge-vision/neural_network/pose_recognition.py con dos
diferencias a propósito:

- Sin `GestureBuffer` (shpd-edge-vision/instructions/gesture_buffer.py) ni
  `config_pose.json`: ese buffer suaviza la clasificación entre frames
  consecutivos porque en shpd-edge-vision corre en cada frame. Acá la
  clasificación local es puntual -- se dispara una sola vez, en el mismo
  momento en que hoy se dispara la llamada a OpenAI (mala postura sostenida
  > umbral) -- así que no hay nada que suavizar entre frames.
- `KeyPointClassifier` expone además del índice ganador (`__call__`, igual
  que en shpd-edge-vision) el array crudo de salida del modelo
  (`predict_proba`): la última capa es softmax sobre 12 clases (confirmado
  en el notebook de entrenamiento), así que esas 12 probabilidades 0-1 se
  pueden escalar directo a porcentaje 0-100 por postura.
"""
import copy
import csv
import itertools
import os

import numpy as np

# En un dispositivo ARM (Raspberry Pi) con tflite_runtime instalado, se usa
# ese paquete liviano. En PC/x86_64, donde no hay wheel de tflite_runtime,
# se cae a tensorflow.lite, que trae el mismo Interpreter. Mismo mecanismo
# de fallback que shpd-edge-vision/neural_network/pose_recognition.py.
try:
    from tflite_runtime.interpreter import Interpreter
except ImportError:
    from tensorflow.lite.python.interpreter import Interpreter

_MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "model")
DEFAULT_MODEL_PATH = os.path.join(_MODEL_DIR, "keypoint_classifier.tflite")
DEFAULT_LABEL_PATH = os.path.join(_MODEL_DIR, "keypoint_classifier_label.csv")

# Landmarks de MediaPipe Pose que usa el modelo (torso + extremidades),
# en el mismo orden usado para entrenarlo en shpd-edge-vision.
INCLUDED_LANDMARKS = [11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]

# Los 12 labels de keypoint_classifier_label.csv (índice == clase de salida
# del softmax) normalizados a la redacción que ya usa el prompt de OpenAI
# en backend/main.py (build_openai_messages/SYSTEM_PROMPT) -- misma
# taxonomía y mismo orden, dos redacciones distintas. Se normaliza acá,
# a la redacción de OpenAI, porque es la que ya está en producción/DB
# (posture_label en PosturaCount/timeline): así posture_label es comparable
# sin importar qué mecanismo clasificó.
LOCAL_TO_CANONICAL_LABELS = [
    "Tronco flexionado hacia delante",           # 0  Tronco flexionado
    "Tronco extendido hacia atras",               # 1  Tronco extendido
    "Inclinación lateral izquierda del tronco",   # 2  Tronco inclinado lateral izquierda
    "Inclinación lateral derecha del tronco",     # 3  Tronco inclinado lateral derecho
    "Mentón apoyado en mano",                     # 4  Mentón en mano
    "Piernas cruzadas",                           # 5  Piernas cruzadas
    "Rodillas elevadas o muy bajas",              # 6  Rodillas elevadas o muy bajas
    "Hombros elevados/encogidos",                 # 7  Elevación escapular
    "Antebrazo sin apoyo",                        # 8  Antebrazo sin apoyo
    "Cabeza adelantada",                          # 9  Cabeza adelantada
    "Hipercifosis torácica",                      # 10 Cifosis torácica aumentada
    "Deslizamiento pélvico anterior",             # 11 Pelvis adelantada respecto respaldo
]


class KeyPointClassifier:
    """Envuelve el intérprete TFLite del modelo de clasificación de posturas."""

    def __init__(self, model_path: str = DEFAULT_MODEL_PATH, num_threads: int = 1):
        self.interpreter = Interpreter(model_path=model_path, num_threads=num_threads)
        self.interpreter.allocate_tensors()
        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()

    def predict_proba(self, landmark_list) -> np.ndarray:
        """Corre la inferencia y devuelve las 12 probabilidades (0-1) del softmax de salida."""
        input_index = self.input_details[0]["index"]
        self.interpreter.set_tensor(input_index, np.array([landmark_list], dtype=np.float32))
        self.interpreter.invoke()
        output_index = self.output_details[0]["index"]
        return np.squeeze(self.interpreter.get_tensor(output_index))

    def __call__(self, landmark_list) -> int:
        """Compatible con shpd-edge-vision: solo el índice de la clase ganadora."""
        return int(np.argmax(self.predict_proba(landmark_list)))


def calc_landmark_list(image_shape, landmarks) -> list:
    """
    Igual que PoseRecognizer.calc_landmark_list de shpd-edge-vision, pero
    recibe `image_shape` (lo que devuelve `frame.shape`, alto x ancho x
    canales) en lugar de la imagen completa -- acá solo hacen falta las
    dimensiones para desnormalizar los landmarks de MediaPipe (0-1) a
    píxeles, no el frame en sí.
    """
    image_height, image_width = image_shape[0], image_shape[1]
    landmark_point = []
    for idx, landmark in enumerate(landmarks):
        if idx in INCLUDED_LANDMARKS:
            landmark_x = min(int(landmark.x * image_width), image_width - 1)
            landmark_y = min(int(landmark.y * image_height), image_height - 1)
            landmark_z = landmark.z
            landmark_point.append([landmark_x, landmark_y, landmark_z])
    return landmark_point


def pre_process_landmark(landmark_list) -> list:
    """Idéntico a PoseRecognizer.pre_process_landmark de shpd-edge-vision."""
    temp_landmark_list = copy.deepcopy(landmark_list)

    base_x, base_y, base_z = 0, 0, 0
    for index, landmark_point in enumerate(temp_landmark_list):
        if index == 0:
            base_x, base_y, base_z = landmark_point[0], landmark_point[1], landmark_point[2]

        temp_landmark_list[index][0] = landmark_point[0] - base_x
        temp_landmark_list[index][1] = landmark_point[1] - base_y
        temp_landmark_list[index][2] = landmark_point[2] - base_z

    temp_landmark_list = list(itertools.chain.from_iterable(temp_landmark_list))

    max_value = max(list(map(abs, temp_landmark_list))) if temp_landmark_list else 0

    def normalize_(n):
        return n / max_value if max_value != 0 else 0

    return list(map(normalize_, temp_landmark_list))


def load_labels(label_path: str = DEFAULT_LABEL_PATH) -> list:
    with open(label_path, encoding="utf-8-sig") as f:
        return [row[0] for row in csv.reader(f)]


class LocalPostureClassifier:
    """
    Clasificador local puntual: dado los `pose_landmarks` crudos de
    MediaPipe de UN frame (los mismos que ya calculó
    `PostureMonitor.process_frame`) y las dimensiones de ese frame, corre
    el pipeline completo (filtrar landmarks -> normalizar -> inferencia
    TFLite) y devuelve el mismo shape que hoy produce json.loads(content)
    en api_analysis_worker: un dict {postura_canónica: porcentaje 0-100}
    con las 12 claves de LOCAL_TO_CANONICAL_LABELS.
    """

    def __init__(self, model_path: str = DEFAULT_MODEL_PATH, label_path: str = DEFAULT_LABEL_PATH):
        self.classifier = KeyPointClassifier(model_path=model_path)
        # Labels crudos del CSV, solo informativos (logging/debug); el dict
        # de salida de `classify` siempre usa LOCAL_TO_CANONICAL_LABELS.
        self.raw_labels = load_labels(label_path)

    def classify(self, pose_landmarks, image_shape) -> dict | None:
        """
        `pose_landmarks`: `results.pose_landmarks` de MediaPipe (None si no
        se detectó a nadie en el frame). `image_shape`: `frame.shape`
        (alto, ancho, canales) de ese mismo frame. Devuelve None si no hay
        landmarks -- nada que clasificar.
        """
        if pose_landmarks is None or image_shape is None:
            return None

        landmark_list = calc_landmark_list(image_shape, pose_landmarks.landmark)
        if not landmark_list:
            return None

        pre_processed_landmark_list = pre_process_landmark(landmark_list)
        probabilities = self.classifier.predict_proba(pre_processed_landmark_list)

        return {
            LOCAL_TO_CANONICAL_LABELS[i]: round(float(p) * 100, 1)
            for i, p in enumerate(probabilities)
        }
