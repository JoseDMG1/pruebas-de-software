"""Bounded conversation contracts; interpretation is never authorization."""

from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    BaseModel, ConfigDict, Field, StrictBool, StrictInt, field_validator, model_validator,
)

Category = Literal['courses', 'teachers', 'assignments', 'grades', 'calendar']


class Runtime(BaseModel):
    model_config = ConfigDict(extra='forbid')
    now: StrictInt = Field(ge=0, le=4102444800)
    timezone: str = Field(min_length=1, max_length=100)

    @field_validator('timezone')
    @classmethod
    def valid_timezone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError('Zona horaria no válida.') from exc
        return value


class Availability(BaseModel):
    model_config = ConfigDict(extra='forbid')
    days: list[StrictInt] = Field(min_length=1, max_length=7)
    start_hour: StrictInt = Field(ge=0, le=23)
    end_hour: StrictInt = Field(ge=1, le=24)

    @model_validator(mode='after')
    def valid_window(self):
        if len(set(self.days)) != len(self.days) or any(not 0 <= day <= 6 for day in self.days):
            raise ValueError('Días no válidos.')
        if self.end_hour <= self.start_hour:
            raise ValueError('Horario no válido.')
        return self


class ConversationPlan(BaseModel):
    model_config = ConfigDict(extra='forbid')
    intent: Literal['social', 'capabilities', 'academic', 'document', 'weekly_plan',
                    'clarify', 'blocked']
    social: Literal['none', 'greeting', 'thanks', 'bye'] = 'none'
    categories: list[Category] = Field(default_factory=list, max_length=5)
    course_mode: Literal['enrolled', 'accessible', 'teaching'] = 'enrolled'
    assignment_filter: Literal['pending', 'submitted', 'all'] = 'pending'
    scope_question: str = Field(default='', max_length=1000)
    document_question: str = Field(default='', max_length=1000)
    follow_up: StrictBool = False
    teacher_confirmation: StrictBool = False
    ambiguous_task: StrictBool = False
    finance: StrictBool = False
    blocked_part: StrictBool = False
    availability: Availability | None = None
    availability_unknown: StrictBool = False
    week_offset: Literal[0, 1] = 0
    week_start: str = Field(default='', max_length=10)
    priority: list[str] = Field(default_factory=list, max_length=20)
    clarification: Literal['intent', 'course', 'task', 'week', 'availability'] = 'intent'

    @model_validator(mode='after')
    def permitted_operations(self):
        if len(set(self.categories)) != len(self.categories):
            raise ValueError('Operaciones duplicadas.')
        if self.intent in {'social', 'capabilities', 'blocked', 'clarify'} and (
            self.categories or self.document_question
        ):
            raise ValueError('Esta intención no permite lecturas.')
        if self.intent == 'social' and self.social == 'none':
            raise ValueError('Falta intención social.')
        if self.intent == 'academic' and not self.categories:
            raise ValueError('Falta operación académica.')
        if self.intent == 'document' and not self.document_question.strip():
            raise ValueError('Falta consulta documental.')
        if self.intent == 'weekly_plan' and (
            self.categories != ['assignments'] or self.assignment_filter != 'pending'
            or self.document_question
        ):
            raise ValueError('Plan semanal requiere tareas pendientes.')
        if self.week_start:
            from datetime import date
            date.fromisoformat(self.week_start)
        if any(not name.strip() or len(name) > 200 for name in self.priority):
            raise ValueError('Prioridad no válida.')
        return self


class Turn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    question: str = Field(min_length=1, max_length=1000)
    answer: str = Field(min_length=1, max_length=4000)


class ConversationState(BaseModel):
    model_config = ConfigDict(extra='forbid')
    topic: ConversationPlan | None = None
    availability: Availability | None = None
    availability_unknown: StrictBool = False
    week_offset: Literal[0, 1] = 0
    week_start: str = Field(default='', max_length=10)


class InterpretationRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    query: str = Field(min_length=1, max_length=1000)
    conversation_context: list[Turn] = Field(default_factory=list, max_length=4)
    runtime: Runtime
    state: ConversationState = Field(default_factory=ConversationState)

    @field_validator('query')
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError('La pregunta está vacía.')
        return value.strip()
