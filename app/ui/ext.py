from typing import Set
from PyQt6 import uic
from PyQt6.QtWidgets import QMainWindow, QMessageBox, QHeaderView, QWidget, QTableView

from sqlmodel import Session, select

from app.db import ENGINE
from app.db.models import (
    Event,
    EventType,
    RoomType,
    WorkRequest,
    WorkRequestType,
    Section
)
from app.ui.dialogs import (
    TypeManagerDialog,
    CreateEventDialog,
    EditEventDialog,
    CreateWorkDialog,
)
from app.ui.dialogs.ext import EditWorksDialog
from app.ui.models import SECTIONS, EventTableModel, WorkRequestTableModel
from app.ui.widgets import Ui_Form


class Table(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__()
        pass


class MainWindow(QMainWindow):
    """
    Represents the Main-Window of this application.
    """

    def __init__(self) -> None:
        """
        Initialize the Main-Window.
        """
        super().__init__()
        uic.loadUi("app/ui/main_window.ui", self)
        
        self.eventsTableView.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.worksTableView.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.desktopTableView.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        self.refreshTableViews()
        
        self.eventsTypeMaximizePushButton.clicked.connect(lambda: self.showTypeManagerDialog(EventType, "Виды мероприятий:"))
        self.worksTypeMaximizePushButton.clicked.connect(lambda: self.showTypeManagerDialog(WorkRequestType, "Виды работ:"))
        self.action_2.triggered.connect(lambda: self.showTypeManagerDialog(RoomType, "Помещения:"))

        self.newEventPushButton.clicked.connect(lambda: self.onCreateClicked(CreateEventDialog()))
        self.newWorkPushButton.clicked.connect(lambda: self.onCreateClicked(CreateWorkDialog()))
        
        self.editSelectedEventsPushButton.clicked.connect(self.onEditSelectedEventsPushButtonClicked)
        self.editSelectedWorksPushButton.clicked.connect(self.onEditSelectedWorksPushButtonClicked)
        
        self.deleteSelectedEventsPushButton.clicked.connect(lambda: self.onDeleteRowsClicked(self.eventsTableView))
        self.deleteSelectedWorksPushButton.clicked.connect(lambda: self.onDeleteRowsClicked(self.worksTableView))

        self.completeSelectedDesktopPushButton.clicked.connect(self.onCompleteSelectedWorksPushButtonClicked)

        with Session(ENGINE) as session:
            workTypeNames = session.exec(select(WorkRequestType.name)).all()

        self.comboBox_12.addItems(workTypeName for workTypeName in workTypeNames)
        self.pushButton_2.clicked.connect(self.filterByWorkTypeName)
        self.resetDesktopFilterButton.clicked.connect(self.resetDesktopFilter)
        
        self.comboBox.addItems(section for section in SECTIONS.values())
        self.pushButton_3.clicked.connect(self.filterByWorkSection)
        self.pushButton_4.clicked.connect(self.resetEventsFilter)

    def showTypeManagerDialog(self, _type, title):
        TypeManagerDialog(_type, title).exec()
        self.refreshTableViews()
    
    events_filter = None
    work_requests_filter = None
        
    def resetDesktopFilter(self):
        self.work_requests_filter = None
        self.comboBox_12.blockSignals(True)
        self.comboBox_12.setCurrentIndex(0)
        self.comboBox_12.blockSignals(False)
        self.refreshDesktop()
        
    def resetEventsFilter(self):
        self.events_filter = None
        self.comboBox.blockSignals(True)
        self.comboBox.setCurrentIndex(0)
        self.comboBox.blockSignals(False)
        self.refreshTableViews()
    
    def filterByWorkSection(self):
        name = self.comboBox.currentText()
        self.events_filter = (Event.section == Section(list(SECTIONS.values()).index(name) + 1))
        self.refreshTableViews()

    def filterByWorkTypeName(self):
        name = self.comboBox_12.currentText()
        with Session(ENGINE) as session:
            type_id = session.exec(
                select(WorkRequestType.id).where(WorkRequestType.name == name)
            ).first()
        self.work_requests_filter = (WorkRequest.type_id == type_id)
        self.refreshDesktop()

    def refreshDesktop(self):
        with Session(ENGINE) as session:
            statement = select(WorkRequest).where(WorkRequest.status == WorkRequest.Status.ACTIVE)
            if self.work_requests_filter is not None:
                statement = statement.where(self.work_requests_filter)
            data: Set[WorkRequest] = session.exec(statement).all()

        self.desktopTableModel = WorkRequestTableModel(data)
        self.desktopTableView.setModel(self.desktopTableModel)
        self.desktopTableView.selectionModel().selectionChanged.connect(
            self.onDesktopTableViewSelectionChanged
        )
        self.completeSelectedDesktopPushButton.setEnabled(False)
        self.onDesktopTableViewSelectionChanged()
        
    # def refreshWorkRequests(self, *args, where=None):

    def refreshTableViews(self, *args):
        self.refreshDesktop()

        with Session(ENGINE) as session:
            statement = select(Event)
            if self.events_filter is not None:
                statement = statement.where(self.events_filter)
            events = session.exec(statement).all()
            workRequests: Set[WorkRequest] = session.exec(select(WorkRequest)).all()
            self.worksTableModel = WorkRequestTableModel(workRequests)
            self.eventsTableModel = EventTableModel(events)

        self.eventsTableView.setModel(self.eventsTableModel)
        self.worksTableView.setModel(self.worksTableModel)

        self.eventsTableView.selectionModel().selectionChanged.connect(
            self.onEventsTableViewSelectionChanged
        )
        self.worksTableView.selectionModel().selectionChanged.connect(
            self.onWorkTableViewSelectionChanged
        )
        
        self.deleteSelectedEventsPushButton.setEnabled(False)
        self.editSelectedEventsPushButton.setEnabled(False)
        self.editSelectedWorksPushButton.setEnabled(False)
        self.deleteSelectedWorksPushButton.setEnabled(False)
        self.onWorkTableViewSelectionChanged()
        self.onEventsTableViewSelectionChanged()

    def onEditSelectedEventsPushButtonClicked(self):
        index = self.eventsTableView.selectedIndexes()[0].row()
        dlg = EditEventDialog(self.eventsTableModel._data[index])
        dlg.exec()

    def onEditSelectedWorksPushButtonClicked(self):
        index = self.worksTableView.selectedIndexes()[0].row()
        dlg = EditWorksDialog(self.worksTableModel._data[index])
        dlg.exec()
        self.refreshDesktop()

    def updateSelection(self, tableView, countLabel, tableModel, deleteButton, editButton):
        selectedIndexesCount = len(
            tableView.selectionModel().selectedRows()
        )
        countLabel.setText(
            f"{selectedIndexesCount} из {tableModel.rowCount()} выбрано"
        )
        deleteButton.setEnabled(selectedIndexesCount)
        if editButton:
            editButton.setEnabled(selectedIndexesCount == 1)

    def onEventsTableViewSelectionChanged(self):
        self.updateSelection(
            self.eventsTableView,
            self.selectedEventsCountLabel,
            self.eventsTableModel,
            self.deleteSelectedEventsPushButton,
            self.editSelectedEventsPushButton
        )

    def onWorkTableViewSelectionChanged(self):
        self.updateSelection(
            self.worksTableView,
            self.selectedWorkCountLabel,
            self.worksTableModel,
            self.deleteSelectedWorksPushButton,
            self.editSelectedWorksPushButton
        )

    def onDesktopTableViewSelectionChanged(self):
        self.updateSelection(
            self.desktopTableView,
            self.selectedDesktopCountLabel,
            self.desktopTableModel,
            self.completeSelectedDesktopPushButton,
            None  # Assuming there's no edit button for desktop items
        )

    def onCompleteSelectedWorksPushButtonClicked(self):
        with Session(ENGINE) as session:
            for index in self.desktopTableView.selectionModel().selectedRows():
                item: WorkRequest = self.desktopTableModel._data[index.row()]
                workRequest: WorkRequest = session.get(WorkRequest, item.id)
                workRequest.status = WorkRequest.Status.COMPLETED
                session.add(workRequest)
                self.desktopTableModel.removeRow(index.row(), delete=False)
            session.commit()
        self.refreshTableViews()
        
    def onCreateClicked(self, dlg):
        dlg.exec()
        self.refreshTableViews()
        
    def onDeleteRowsClicked(self, tableView: QTableView):
        if self.showConfirmationWarning() != QMessageBox.StandardButton.Ok:
            return

        for index in tableView.selectionModel().selectedRows():
            tableView.model().removeRow(index.row())

    def showConfirmationWarning(self):
        return QMessageBox.warning(
            self.parent(),
            "Удаление объектов",
            "Вы действительно хотите удалить выбранные объекты?",
            defaultButton=QMessageBox.StandardButton.Cancel,
        )


__all__ = ["MainWindow"]
