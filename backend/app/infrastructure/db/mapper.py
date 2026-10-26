import copy
import dataclasses
from dataclasses import dataclass
from typing import Any

from sqlalchemy import event
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import (
    Account,
    BulkTask,
    BulkTaskItem,
    ChatMessage,
    Comment,
    MessageStatSnapshot,
    PanelUser,
    Proxy,
    TgUser,
    TrackedMessage,
)
from app.infrastructure.db.models import (
    AccountModel,
    Base,
    BulkTaskItemModel,
    BulkTaskModel,
    CommentModel,
    MessageModel,
    MessageStatSnapshotModel,
    PanelUserModel,
    ProxyModel,
    TgUserModel,
    TrackedMessageModel,
)

MODELS: dict[type, type[Base]] = {
    PanelUser: PanelUserModel,
    Proxy: ProxyModel,
    Account: AccountModel,
    BulkTask: BulkTaskModel,
    BulkTaskItem: BulkTaskItemModel,
    TrackedMessage: TrackedMessageModel,
    MessageStatSnapshot: MessageStatSnapshotModel,
    Comment: CommentModel,
    TgUser: TgUserModel,
    ChatMessage: MessageModel,
}
ENTITIES: dict[type[Base], type] = {model: entity for entity, model in MODELS.items()}
RELATIONSHIPS: dict[type[Base], dict[str, bool]] = {
    AccountModel: {"proxy": False},
    BulkTaskModel: {"items": True},
    TrackedMessageModel: {"snapshots": True},
    MessageModel: {"tg_user": False},
}


def _columns(model_cls: type[Base]) -> tuple[str, ...]:
    return tuple(a.key for a in sa_inspect(model_cls).column_attrs)


COLUMNS: dict[type[Base], tuple[str, ...]] = {m: _columns(m) for m in ENTITIES}
INIT_FIELDS: dict[type, frozenset[str]] = {
    e: frozenset(f.name for f in dataclasses.fields(e) if f.init) for e in MODELS
}


def _value(v: Any) -> Any:
    return copy.deepcopy(v) if isinstance(v, (list, dict)) else v


@dataclass(eq=False)
class _Entry:
    entity: Any
    model: Base
    snapshot: dict[str, Any]


class EntityTracker:

    def __init__(self, session: AsyncSession):
        self._session = session
        self._by_model: dict[int, _Entry] = {}
        self._by_entity: dict[int, _Entry] = {}
        event.listen(session.sync_session, "after_flush_postexec", self._after_flush)

    def entity(self, model: Base | None) -> Any:
        if model is None:
            return None
        entry = self._by_model.get(id(model))
        if entry is None:
            cls = ENTITIES[type(model)]
            values = {c: _value(getattr(model, c)) for c in COLUMNS[type(model)]}
            entity = cls(**{k: v for k, v in values.items() if k in INIT_FIELDS[cls]})
            for k, v in values.items():
                if k not in INIT_FIELDS[cls]:
                    setattr(entity, k, v)
            entry = self._track(entity, model)
        self._attach(entry)
        return entry.entity

    def entities(self, models) -> list:
        return [self.entity(m) for m in models]

    def _attach(self, entry: _Entry) -> None:
        unloaded = sa_inspect(entry.model).unloaded
        for name, many in RELATIONSHIPS.get(type(entry.model), {}).items():
            if name in unloaded:
                continue
            related = getattr(entry.model, name)
            setattr(
                entry.entity,
                name,
                self.entities(related) if many else self.entity(related),
            )

    def model(self, entity: Any) -> Base:
        entry = self._by_entity.get(id(entity))
        if entry is None:
            raise LookupError(
                f"{type(entity).__name__} does not belong to this unit of work"
            )
        return entry.model

    def add(self, entity: Any) -> Base:
        model_cls = MODELS[type(entity)]
        values = {c: _value(getattr(entity, c)) for c in COLUMNS[model_cls]}
        if values.get("id") is None:
            values.pop("id", None)
        model = model_cls(**values)
        self._session.add(model)
        entry = self._track(entity, model)
        for name, many in RELATIONSHIPS.get(model_cls, {}).items():
            if not hasattr(entity, name):
                setattr(entity, name, [] if many else None)
        return entry.model

    def forget(self, entity: Any) -> None:
        entry = self._by_entity.pop(id(entity), None)
        if entry:
            self._by_model.pop(id(entry.model), None)

    def clear(self) -> None:
        self._by_model.clear()
        self._by_entity.clear()

    async def refresh_relationship(self, entity: Any, name: str) -> None:
        entry = self._by_entity[id(entity)]
        self.sync()
        await self._session.flush()
        await self._session.refresh(entry.model, [name])
        self._attach(entry)

    def sync(self) -> None:
        for entry in self._by_entity.values():
            for c in COLUMNS[type(entry.model)]:
                v = getattr(entry.entity, c)
                if v != entry.snapshot.get(c):
                    setattr(entry.model, c, _value(v))
                    entry.snapshot[c] = _value(v)

    def _track(self, entity: Any, model: Base) -> _Entry:
        snapshot = {c: _value(getattr(entity, c)) for c in COLUMNS[type(model)]}
        entry = _Entry(entity, model, snapshot)
        self._by_model[id(model)] = entry
        self._by_entity[id(entity)] = entry
        return entry

    def _after_flush(self, _session, _context) -> None:
        for entry in self._by_entity.values():
            if (
                entry.snapshot.get("id") is None
                and "id" not in sa_inspect(entry.model).unloaded
            ):
                model_id = entry.model.id
                if model_id is not None:
                    entry.entity.id = model_id
                    entry.snapshot["id"] = model_id
