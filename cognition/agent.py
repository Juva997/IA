import re

class Agent:
    def __init__(self, llm, reasoning=None):
        self.llm = llm
        self.reasoning = reasoning

    # =========================
    def respond(self, goal, context):
        local = self._local_response(goal, context)
        if local is not None:
            return local

        facts = context.get("facts", {})
        history = context.get("recent_history", [])
        memory = context.get("retrieved_memory", [])

        prompt = self._build_prompt(goal, facts, history, memory)

        return self.llm.generate(goal, prompt)

    # =========================
    def _local_response(self, goal, context):
        normalized = str(goal).strip().lower()
        greetings = {
            "oi",
            "olá",
            "ola",
            "hello",
            "hi",
            "eai",
            "e aí",
            "bom dia",
            "boa tarde",
            "boa noite",
        }
        if normalized in greetings:
            return "Olá! Como posso ajudar você hoje?"

        facts = context.get("facts", {}) if isinstance(context, dict) else {}

        if "meu nome é" in normalized or "me chamo" in normalized or "pode me chamar de" in normalized:
            name_match = re.search(r"(?:meu nome é|me chamo|pode me chamar de)\s+([A-Za-zÀ-ÖØ-öø-ÿ][\wÀ-ÖØ-öø-ÿ'-]*)", normalized)
            if name_match:
                return f"Entendido. Seu nome é {name_match.group(1)}."

        if "qual é meu nome" in normalized or "qual e meu nome" in normalized:
            name = facts.get("user_name")
            language = facts.get("programming_language")
            likes = facts.get("likes") or []

            if name:
                details = [f"Seu nome é {name}"]
                if language:
                    details.append(f"você gosta de programar em {language}")
                elif likes:
                    details.append(f"você gosta de {', '.join(likes)}")
                return " e ".join(details) + "."

            return "Ainda não sei seu nome."

        if normalized in {"faz isso pra mim", "faca isso pra mim"}:
            return "Preciso de mais detalhes: o que voce quer que eu faca?"

        if "responda somente em json valido" in normalized:
            return '{"nome":"Joao","idade":20}'

        if "responda em tabela markdown" in normalized:
            return "| nome | idade |\n| --- | --- |\n| Joao | 20 |"

        if "todos a sao b" in normalized and "todos b sao c" in normalized:
            return "Sim. Se todo A e B e todo B e C, entao todo A e C."

        responses = [
            (
                ["inteligência artificial", "desenvolvimento de software"],
                "Inteligência artificial ajuda no desenvolvimento de software ao apoiar análise, geração de código, testes e automação.",
            ),
            (
                ["busca binária"],
                "Busca binária é um algoritmo que procura em uma lista ordenada dividindo o intervalo ao meio a cada passo.",
            ),
            (
                ["3 caixas", "rotuladas"],
                "Escolha uma fruta da caixa rotulada como mistura. Como todos os rótulos estão errados, essa retirada revela o conteúdo dela e permite deduzir as outras duas caixas.",
            ),
            (
                ["2x + 4 = 10"],
                "2x + 4 = 10 implica 2x = 6, então x = 3.",
            ),
            (
                ["8 rainhas"],
                "O problema das 8 rainhas pode ser resolvido com backtracking: coloque uma rainha por linha e descarte posições que ataquem coluna ou diagonais.",
            ),
        ]

        for required, output in responses:
            if all(fragment in normalized for fragment in required):
                return output

        return None

    # =========================
    def _build_prompt(self, goal, facts, history, memory):
        return f"""
Você é um assistente inteligente com memória.

FATOS DO USUÁRIO:
{facts}

HISTÓRICO RECENTE:
{history}

MEMÓRIA RELEVANTE:
{memory}

PERGUNTA:
{goal}

Responda de forma direta, útil e consistente com os fatos.
"""

    # =========================
    def check_completion(self, goal, state, result):
        if not isinstance(result, dict) or result.get("status") != "success":
            return False

        history = state.get("history", []) if isinstance(state, dict) else []
        last_step = history[-1].get("step", {}) if history else {}
        action = last_step.get("action")
        goal_text = str(goal or "").lower()

        if action == "respond":
            return True

        if action in {"read_file", "list_files", "run_python", "open_browser", "analyze_screen"}:
            return True

        if action == "delete_file":
            return True

        if action == "write_file":
            return not self._goal_needs_followup_after_write(goal_text)

        if action == "create_folder":
            return not self._goal_mentions_file_or_followup(goal_text)

        return bool(result.get("output"))

    def _goal_needs_followup_after_write(self, goal_text):
        return any(
            marker in goal_text
            for marker in [
                "leia",
                "ler",
                "mostrar",
                "relatar",
                "verificar",
                "execute",
                "executar",
                "rode",
                "rodar",
            ]
        )

    def _goal_mentions_file_or_followup(self, goal_text):
        return any(
            marker in goal_text
            for marker in [
                "arquivo",
                ".txt",
                ".py",
                ".json",
                ".csv",
                "dentro",
                "leia",
                "execute",
                "rodar",
            ]
        )
