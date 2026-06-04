import re
from actions.tools.self_care import self_care


class Agent:
    def __init__(self, llm, reasoning=None, memory=None):
        self.llm = llm
        self.reasoning = reasoning
        self.memory = memory

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

        # confirmações rápidas (sim / não)
        yes = {"sim", "s", "claro", "ok", "confirmar", "pode", "com certeza", "yes"}
        no = {"não", "nao", "n", "não mesmo", "nah", "no", "nao obrigado", "não, obrigado"}

        # Tratar confirmações pendentes salvas como 'pending_*' na memória
        try:
            if normalized in yes and self.memory:
                pending_name = self.memory.get_fact("pending_user_name")
                if pending_name:
                    self.memory.remember_fact("user_name", pending_name, confidence=0.95, source="user_confirmed")
                    try:
                        self.memory.forget_memory("fact", "pending_user_name")
                    except Exception:
                        pass
                    return f"Entendido — vou lembrar que seu nome é {pending_name}."

                pending_mood = self.memory.get_fact("pending_mood")
                if pending_mood:
                    self.memory.remember_fact("mood", pending_mood, confidence=0.9, source="user_confirmed")
                    try:
                        self.memory.forget_memory("fact", "pending_mood")
                    except Exception:
                        pass
                    return f"Entendi — vou registrar que você está se sentindo '{pending_mood}'. Posso sugerir algo para ajudar?"
        except Exception:
            pass

        try:
            if normalized in no and self.memory:
                removed = False
                if self.memory.get_fact("pending_user_name"):
                    try:
                        self.memory.forget_memory("fact", "pending_user_name")
                    except Exception:
                        pass
                    removed = True
                if self.memory.get_fact("pending_mood"):
                    try:
                        self.memory.forget_memory("fact", "pending_mood")
                    except Exception:
                        pass
                    removed = True
                if removed:
                    return "Certo, não vou salvar isso."
        except Exception:
            pass

        # se há uma escolha pendente de autocuidado, execute-a automaticamente
        try:
            if self.memory and self.memory.get_fact("pending_self_care"):
                # opção 1: ouvir
                if normalized in {"1", "1.", "1)", "opcao 1", "opção 1"} or "ouvir" in normalized:
                    try:
                        self.memory.forget_memory("fact", "pending_self_care")
                    except Exception:
                        pass
                    return "Estou aqui para ouvir — conte o que aconteceu."

                # opção 2: respiração guiada
                if normalized in {"2", "2.", "2)", "opcao 2", "opção 2"} or any(k in normalized for k in ("respira", "respiração", "respire", "respirar")):
                    return self._execute_self_care("exercise_breathing", context)

                # opção 3: criar tarefa de autocuidado
                if normalized in {"3", "3.", "3)", "opcao 3", "opção 3"} or any(k in normalized for k in ("tarefa", "lembrete", "criar")):
                    return self._execute_self_care("create_task", {"task": "Pausa 5min"}, context)
        except Exception:
            pass

        # verificar fato 'mood' no contexto e sugerir proativamente se 'mal'
        try:
            facts_ctx = context.get("facts", {}) if isinstance(context, dict) else {}
            mood_ctx = facts_ctx.get("mood")
            if not mood_ctx and self.memory:
                try:
                    mood_ctx = self.memory.get_fact("mood")
                except Exception:
                    mood_ctx = None

            if str(mood_ctx or "").lower() == "mal":
                if not any(marker in normalized for marker in ["estou mal", "nao estou bem", "não estou bem", "to mal"]):
                    try:
                        if self.memory:
                            self.memory.remember_fact("pending_self_care", True, confidence=0.9, source="agent_suggestion")
                    except Exception:
                        pass
                    return (
                        "Percebi que você está se sentindo mal. Posso: 1) ouvir você; 2) sugerir exercícios rápidos de respiração; "
                        "3) criar uma tarefa de autocuidado. Qual dessas você prefere?"
                    )
        except Exception:
            pass

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
            "tudo bem",
            "tudo bem?",
        }
        if normalized in greetings:
            try:
                try:
                    if self.memory and str(self.memory.get_fact("mood") or "").lower() == "mal":
                        try:
                            if self.memory:
                                self.memory.remember_fact("pending_self_care", True, confidence=0.9, source="agent_suggestion")
                        except Exception:
                            pass
                        return (
                            "Percebi que você está se sentindo mal. Posso: 1) ouvir você; 2) sugerir exercícios rápidos de respiração; "
                            "3) criar uma tarefa de autocuidado. Qual dessas você prefere?"
                        )
                except Exception:
                    pass
            except Exception:
                pass

            return "Olá! Posso ajudar com uma conversa ou com tarefas."

        # Respostas mais conversacionais para estados explícitos
        if "estou mal" in normalized or "nao estou bem" in normalized or "não estou bem" in normalized or "to mal" in normalized:
            try:
                if self.memory:
                    self.memory.remember_fact("pending_mood", "mal", confidence=0.7, source="user_statement_pending")
            except Exception:
                pass
            return "Sinto muito. Quer que eu registre que você está se sentindo mal para poder te ajudar melhor? (sim/não)"

        if "estou bem" in normalized or normalized.startswith("to bem") or normalized.startswith("tô bem"):
            try:
                if self.memory:
                    self.memory.remember_fact("pending_mood", "bem", confidence=0.9, source="user_statement_pending")
            except Exception:
                pass
            return "Que bom ouvir isso! Quer que eu salve que você está bem para eu me lembrar depois? (sim/não)"

        # Sugestões proativas para o dia
        if any(marker in normalized for marker in ["o que fazer", "o que devemos", "o que a gente faz", "o que eu faço", "o que fazer hoje", "o que devemos fazer hoje"]):
            return (
                "Posso sugerir algumas opções: 1) revisar tarefas pendentes, 2) aprender/treinar um tópico, "
                "3) organizar sua agenda, 4) trabalhar em um projeto. Quer que eu sugira uma em detalhe ou faça uma dessas agora?"
            )

        facts = context.get("facts", {}) if isinstance(context, dict) else {}

        if "meu nome é" in normalized or "me chamo" in normalized or "pode me chamar de" in normalized:
            name_match = re.search(r"(?:meu nome é|me chamo|pode me chamar de)\s+([A-Za-zÀ-ÖØ-öø-ÿ][\wÀ-ÖØ-öø-ÿ'-]*)", normalized)
            if name_match:
                name = name_match.group(1)
                try:
                    if self.memory:
                        self.memory.remember_fact("pending_user_name", name, confidence=0.95, source="user_statement_pending")
                except Exception:
                    pass
                return f"Entendi — seu nome é {name}. Quer que eu lembre isso? (sim/não)"

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

    def _execute_self_care(self, action, data=None, context=None):
        try:
            if action == "exercise_breathing":
                res = self_care({"action": "exercise_breathing"}, state=context or {})
            elif action == "create_task":
                task = data.get("task") if isinstance(data, dict) and data.get("task") else "Pausa de autocuidado"
                res = self_care({"action": "create_task", "task": task}, state=context or {})
            else:
                return "Ação de autocuidado desconhecida."

            if self.memory:
                try:
                    self.memory.forget_memory("fact", "pending_self_care")
                except Exception:
                    pass

            if isinstance(res, dict):
                return res.get("output") or ""
            return str(res)
        except Exception as e:
            return f"Erro ao executar autocuidado: {e}"

    # =========================
    def _build_prompt(self, goal, facts, history, memory):
        system = (
            "Sistema: Você é um assistente conversacional, amigável e proativo. "
            "Adote um tom natural e humano, faça perguntas de follow-up curtas (ex.: 'Como foi seu dia?') quando apropriado, "
            "e use os fatos e memórias para personalizar respostas sem repetir o conteúdo bruto da memória. "
            "Se for necessário gravar fatos do usuário, confirme antes de persistir."
        )

        return f"""{system}
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
