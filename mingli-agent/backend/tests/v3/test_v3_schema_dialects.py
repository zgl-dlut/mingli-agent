from sqlalchemy.dialects import mysql, sqlite
from sqlalchemy.schema import CreateTable

from app.models.person import Person
from app.models.subscription import Subscription
from app.models.usage_counter import UsageCounter
from app.models.report import Report
from app.models.persona import Persona
from app.models.persona_conversation import PersonaConversation
from app.models.persona_message import PersonaMessage
from app.models.persona_memory import PersonaMemory
from app.models.safety_event import SafetyEvent


def _compile(table, dialect) -> str:
    return str(CreateTable(table).compile(dialect=dialect))


def test_v3_tables_compile_for_sqlite():
    dialect = sqlite.dialect()
    for table in (Person.__table__, Subscription.__table__, UsageCounter.__table__):
        sql = _compile(table, dialect)
        assert "CREATE TABLE" in sql


def test_v3_tables_compile_for_mysql_8():
    dialect = mysql.dialect()
    for table in (Person.__table__, Subscription.__table__, UsageCounter.__table__):
        sql = _compile(table, dialect)
        assert "CREATE TABLE" in sql
    assert "JSON" in _compile(Person.__table__, dialect)
