class PromptBuilder:
    """Rascunho de PromptBuilder.

    Objetivo: isolar os templates e construção do prompt usado pelo Planner.
    Este arquivo é um rascunho inicial para revisão — deve conter o texto
    do prompt em recursos separados e helpers de interpolação.
    """

    def __init__(self):
        pass

    def build_prompt(self, goal: str, tools: str) -> str:
        # Implementar construção de prompt baseado no original em planner.py
        prompt = f"Objetivo: {goal}\n\nFerramentas:\n{tools}\n"
        prompt += "\n(este é um rascunho de PromptBuilder — substituir pelo conteúdo real)"
        return prompt
