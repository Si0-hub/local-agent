from dataclasses import dataclass, field


@dataclass
class Plan:
    steps: list[str] = field(default_factory=list)

    def __iter__(self):
        return iter(self.steps)

    def __len__(self):
        return len(self.steps)

    def __bool__(self):
        return bool(self.steps)


@dataclass
class StepResult:
    step: str
    output: str
    success: bool = True


@dataclass
class Verdict:
    ok: bool
    feedback: str = ""
    raw: str = ""
