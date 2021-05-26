import typing
from datetime import datetime
from enum import Enum, auto

from pydantic import BaseModel, constr, Field

from models import ChatMessage
from utils import utcnow


class ActionType(Enum):
    message = auto()
    add_dj = auto()

    add_queue = auto()

    error = auto()


class ChatActionSchema(BaseModel):
    date: datetime = Field(default_factory=utcnow)
    action_type: ActionType
    sender: str


class MessageSchema(ChatActionSchema):
    message: constr(min_length=ChatMessage.message.min_length,
                    max_length=ChatMessage.message.max_length)
    action_type = ActionType.message


class AddDJSchema(ChatActionSchema):
    who: str
    action_type = ActionType.add_dj


class AddQueueSchema(ChatActionSchema):
    track: str
    action_type = ActionType.add_queue


class ErrorSchema(ChatActionSchema):
    action_type = ActionType.error
    errors: typing.List[typing.Dict[str, typing.Any]] = None
    message: str = None
    sender: str = None
