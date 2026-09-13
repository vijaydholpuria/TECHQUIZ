from pydantic import BaseModel, Field, field_validator


class LoginPayload(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class QuestionInput(BaseModel):
    question_text: str = Field(min_length=1, max_length=2000)
    option_a: str = Field(min_length=1, max_length=500)
    option_b: str = Field(min_length=1, max_length=500)
    option_c: str = Field(min_length=1, max_length=500)
    option_d: str = Field(min_length=1, max_length=500)
    correct_option: str
    time_limit: int = Field(ge=1, le=300)

    @field_validator("correct_option")
    @classmethod
    def valid_option(cls, value):
        value = value.upper()
        if value not in {"A", "B", "C", "D"}:
            raise ValueError("Correct option must be A, B, C, or D.")
        return value


class QuizInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    questions: list[QuestionInput] = Field(min_length=1, max_length=100)


class JoinInput(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    participant_token: str | None = Field(default=None, min_length=20, max_length=100)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        cleaned = " ".join(value.strip().split())
        if not cleaned:
            raise ValueError("Name is required.")
        if any(ord(character) < 32 for character in cleaned):
            raise ValueError("Name contains invalid characters.")
        return cleaned


class AnswerInput(BaseModel):
    participant_token: str = Field(min_length=20, max_length=100)
    question_id: str = Field(min_length=1, max_length=50)
    selected_option: str

    @field_validator("selected_option")
    @classmethod
    def valid_answer(cls, value):
        value = value.upper()
        if value not in {"A", "B", "C", "D"}:
            raise ValueError("Invalid answer.")
        return value
