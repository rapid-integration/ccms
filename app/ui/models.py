from typing import Any, Set, TypeVar, Generic

from PyQt6.QtCore import (
    QObject,
    Qt,
    QAbstractListModel,
    QAbstractTableModel,
    QModelIndex,
)
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QMessageBox
from sqlmodel import Session, select

from app.db import ENGINE
from app.db.models import BaseNamedModel, EventType, Event, WorkRequest, WorkRequestType, RoomType, WorkRequestStatus

TBaseNamedModel = TypeVar("TBaseNamedModel", bound=BaseNamedModel)

SECTIONS = {
    1: "Развлечение",
    2: "Просвещение",
    3: "Образование"
}

STATUSES = {
    1: "Черновик",
    2: "Активно",
    3: "Выполнено"
}


class TypeListModel(Generic[TBaseNamedModel], QAbstractListModel):
    def __init__(
        self, data: Set[TBaseNamedModel], parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._data = data

    def rowCount(self, _: QModelIndex = ...) -> int:
        return len(self._data)

    def data(self, index: QModelIndex, role: int = ...) -> Any:
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return self._data[index.row()].name

    def insertRow(self, row: int, parent: QModelIndex = QModelIndex()) -> bool:
        self.beginInsertRows(parent, row, row)

        name = f"Объект ({self.rowCount()})"

        if self.isUniqueNameConstraintFailed(name):
            self._showUniqueNameConstraintWarning(name)
            return False

        with Session(ENGINE) as session:
            newObj: TBaseNamedModel = self._getGenericType()(name=name)
            session.add(newObj)
            session.commit()
            session.refresh(newObj)

        self._data.append(newObj)

        self.endInsertRows()
        return True

    def removeRow(self, row: int, parent: QModelIndex = QModelIndex()) -> bool:
        self.beginRemoveRows(parent, row, row)

        item = self._data[row]

        if (
            self._showObjectDeletionConfirmation(item.name)
            != QMessageBox.StandardButton.Ok
        ):
            return False

        self._data.remove(item)

        with Session(ENGINE) as session:
            obj: TBaseNamedModel = session.get(self._getGenericType(), item.id)
            session.delete(obj)
            session.commit()

        self.endRemoveRows()
        return True

    def setData(self, index: QModelIndex, value: Any, role: int = ...) -> bool:
        if role == Qt.ItemDataRole.EditRole:
            return self.editData(index, value)

    def editData(self, index: QModelIndex, value: Any) -> bool:
        item = self._data[index.row()]

        if item.name == value:
            return False

        if self.isUniqueNameConstraintFailed(value):
            self._showUniqueNameConstraintWarning(value)
            return False

        item.name = value

        with Session(ENGINE) as session:
            obj: TBaseNamedModel = session.get(self._getGenericType(), item.id)
            obj.name = value
            session.add(obj)
            session.commit()

        self.dataChanged.emit(index, index)
        return True

    def flags(self, _: QModelIndex) -> Qt.ItemFlag:
        return (
            Qt.ItemFlag.ItemIsEditable
            | Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
        )

    def isUniqueNameConstraintFailed(self, name: str) -> bool:
        return any(item.name == name for item in self._data)

    def _showUniqueNameConstraintWarning(self, name: str) -> None:
        QMessageBox.critical(
            self.parent(), "Ошибка", f"Объект названием '{name}' уже был создан ранее."
        )

    def _showObjectDeletionConfirmation(self, name: str) -> bool:
        return QMessageBox.warning(
            self.parent(),
            "Подтверждение удаления объекта",
            f"Вы действительно хотите удалить '{name}'?",
            defaultButton=QMessageBox.StandardButton.Close,
        )

    def _getGenericType(self) -> TBaseNamedModel:
        return self.__orig_class__.__args__[0]


class WorkTableModel(QAbstractTableModel):
    def __init__(self, data: Set[WorkRequest], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.ddata = data
        self._headers = (
            "Помещение",
            "Разновидность",
            "Мероприятие",
            "Статус",
            "Дедлайн",
            "Дата создания",
            "Описание",
        )

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = ...
    ) -> Any:
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
        ):
            return self._headers[section]
        return super().headerData(section, orientation, role)

    def data(self, index: QModelIndex, role: int = ...) -> Any:
        work = self.ddata[index.row()]
        if role == Qt.ItemDataRole.BackgroundRole:
            match work.status.value:
                case 2:
                    return QColor("lightpink")
                case 3:
                    return QColor("lightgray")
        if role == Qt.ItemDataRole.DisplayRole:
            match index.column():
                case 0:
                    with Session(ENGINE) as session:
                        return session.exec(
                            select(RoomType.name).where(RoomType.id == work.room_id)
                        ).first()
                case 1:
                    with Session(ENGINE) as session:
                        return session.exec(
                            select(WorkRequestType.name).where(WorkRequestType.id == work.type_id)
                        ).first()
                case 2:
                    with Session(ENGINE) as session:
                        return session.exec(
                            select(Event.name).where(Event.id == work.event_id)
                        ).first()
                case 3:
                    return STATUSES[work.status.value]
                case 4:
                    return work.deadline.strftime("%d.%m.%Y %H:%M")
                case 5:
                    return work.created_at.strftime("%d.%m.%Y %H:%M")
                case 6:
                    return work.description

    def removeRow(self, row: int, delete=True, parent: QModelIndex = QModelIndex()) -> bool:
        self.beginRemoveRows(parent, row, row)
        with Session(ENGINE) as session:
            item = self.ddata[row]
            self.ddata.remove(item)
            if delete:
                workType = session.get(WorkRequest, item.id)
                session.delete(workType)
                session.commit()            
        self.endRemoveRows()
        return True

    def rowCount(self, _: QModelIndex = ...) -> int:
        return len(self.ddata)

    def columnCount(self, _: QModelIndex = ...) -> int:
        return len(self._headers)

    def flags(self, _: QModelIndex) -> Qt.ItemFlag:
        return Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled


class EventTableModel(QAbstractTableModel):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        with Session(ENGINE) as session:
            self.ddata = session.exec(select(Event)).all()
        self.__headers = (
            "Заголовок",
            "Пространство",
            "Разновидность",
            "Помещение",
            "Дата начала",
            "Описание",
        )

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = ...
    ) -> Any:
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
        ):
            return self.__headers[section]
        return super().headerData(section, orientation, role)

    def data(self, index: QModelIndex, role: int = ...) -> Any:
        if role == Qt.ItemDataRole.DisplayRole:
            event = self.ddata[index.row()]
            match index.column():
                case 0:
                    return event.name
                case 1:
                    return SECTIONS[event.section.value]
                case 2:
                    with Session(ENGINE) as session:
                        return session.exec(
                            select(EventType.name).where(EventType.id == event.type_id)
                        ).first()
                case 3:
                    with Session(ENGINE) as session:
                        return session.exec(
                            select(RoomType.name).where(RoomType.id == event.room_id)
                        ).first()
                case 4:
                    return event.start_at.strftime("%d.%m.%Y %H:%M")
                case 5:
                    return event.description

    def removeRow(self, row: int, parent: QModelIndex = QModelIndex()) -> bool:
        self.beginRemoveRows(parent, row, row)
        with Session(ENGINE) as session:
            item = self.ddata[row]
            eventType = session.get(Event, item.id)
            session.delete(eventType)
            self.ddata.remove(item)
            session.commit()
        self.endRemoveRows()
        return True

    def rowCount(self, _: QModelIndex = ...) -> int:
        return len(self.ddata)

    def columnCount(self, _: QModelIndex = ...) -> int:
        return len(self.__headers)

    def flags(self, _: QModelIndex) -> Qt.ItemFlag:
        return Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled


__all__ = ["TypeListModel", "EventTableModel", "WorkTableModel"]
