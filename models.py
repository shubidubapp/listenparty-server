from datetime import datetime

from mongoengine import EmbeddedDocument, Document
from mongoengine.fields import EnumField, ReferenceField, StringField, ListField, EmbeddedDocumentField, BooleanField, \
    LazyReferenceField, IntField, URLField, DateTimeField

from extensions import login_manager
from utils import utcnow, ACTIVITY


class Token(EmbeddedDocument):
    access_token = StringField()
    refresh_token = StringField()
    expires_at = IntField()

    def to_token(self):
        return {"access_token": self.access_token, "refresh_token": self.refresh_token,
                "expires_at": self.expires_at}

    def set_from_dict(self, d):
        self.access_token = d["access_token"]
        self.refresh_token = d["refresh_token"]
        self.expires_at = d["expires_at"]


class User(Document):
    username = StringField(unique=True)
    display_name = StringField()
    img = URLField()
    activity = EnumField(ACTIVITY, default=ACTIVITY.NONE)
    stream = ReferenceField('Stream')

    token = EmbeddedDocumentField("Token")

    def __repr__(self):
        return f"<User::{self.username}>"

    def get_id(self):
        return self.pk.__str__()

    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return True

    @property
    def is_anonymous(self):
        return False

    meta = {'indexes': [
        {'fields': ['$username', "$display_name"],
         'default_language': 'english',
         'weights': {'username': 5, 'display_name': 5}
         }
    ]}


class Stream(Document):
    streamer = ReferenceField('User')
    active = BooleanField(default=True)

    listeners = ListField(ReferenceField("User"), default=[])

    name = StringField()

    date = DateTimeField(default=datetime.utcnow)

    dj = ListField(ReferenceField("User"), default=[])

    meta = {'indexes': [
        {'fields': ['$name'],
         'default_language': 'english',
         'weights': {'name': 5}
         }
    ]}


class ChatAction(Document):
    sender = ReferenceField("User")
    stream = LazyReferenceField("Stream")
    date = DateTimeField(default=utcnow)

    meta = {'allow_inheritance': True}


class ChatMessage(ChatAction):
    message = StringField(max_length=231, required=True)


class ChatDJ(ChatAction):
    who = ReferenceField("User")


class ChatQueue(ChatAction):
    track = StringField()


class Log(Document):
    username = StringField()
    user = LazyReferenceField("User")
    log = StringField()


@login_manager.user_loader
def load_user(user_id):
    return User.objects.get(pk=user_id)
