import pyttsx3
import speech_recognition as sr

from core.orchestrator import Orchestrator


class VoiceInterface:
    def __init__(self):
        self.orch = Orchestrator()
        self.recognizer = sr.Recognizer()
        self.tts = pyttsx3.init()

    def listen(self):
        with sr.Microphone() as source:
            print("Ajustando para ruido ambiente...")
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
            print("Fale seu objetivo...")
            try:
                audio = self.recognizer.listen(source, timeout=7, phrase_time_limit=15)
            except sr.WaitTimeoutError:
                print("Tempo esgotado. Nao foi possivel ouvir nada.")
                return None

        try:
            text = self.recognizer.recognize_google(audio, language="pt-BR")
            print(f"Voce disse: {text}")
            return text
        except sr.UnknownValueError:
            print("Nao entendi o audio. Tente novamente.")
            return None
        except sr.RequestError as e:
            print(f"Erro no servico de voz: {e}")
            return None
        except Exception as e:
            print(f"Falha no reconhecimento de voz: {e}")
            return None

    def speak(self, text):
        self.tts.say(text)
        self.tts.runAndWait()

    def run(self):
        while True:
            goal = self.listen()

            if not goal:
                continue

            if "sair" in goal.lower():
                break

            response = self.orch.handle_user_query(goal)

            print("Assistente:", response)
            self.speak(response)

    def _format_response(self, result):
        try:
            if isinstance(result, dict):
                return str(result.get("output", result))
            return str(result)
        except Exception:
            return "Tarefa concluida"


def start_voice():
    v = VoiceInterface()
    v.run()
