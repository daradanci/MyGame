from dataclasses import dataclass
from typing import Optional

@dataclass
class UserObject:
    user_id: int
    first_name: str
    last_name: Optional[str]
    username: Optional[str]




@dataclass
class UpdateObject:
    message_id: Optional[int]
    chat_id: int
    user_id: int
    body: str
    user_info: Optional[UserObject]


@dataclass
class Update:
    update_id: int
    object: UpdateObject


@dataclass
class Message:
    chat_id: int
    text: str
