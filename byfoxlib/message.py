class Message:
    def __init__(self, *text: str, command: str = "say"):
        self.command = command
        self.text = list(text)

    def __add__(self, other: str):
        self.text.append(other)

    def __str__(self):
        return ';'.join(f"{self.command} \"{text}\"" for text in self.text)
