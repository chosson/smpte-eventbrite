import os
import sys
import json
import time
import shutil

import PySide6
from PySide6 import QtUiTools
from PySide6.QtCore import Qt, QSignalBlocker
from PySide6.QtWidgets import QMainWindow, QTableWidgetItem, QComboBox

from eventbrite_manager import *


def checkToBool(checkState):
	return False if checkState == Qt.Unchecked else True

def boolToCheck(boolean):
	return Qt.Checked if boolean else Qt.Unchecked


# Importation des types venant du .ui
uiclass, baseclass = QtUiTools.loadUiType("MainWindow.ui")

class MainWindow(uiclass, baseclass):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

		self.eventbrite = EventbriteManager()

		# Chargement du GUI
		self.setupUi(self)
		# Config des affichages
		self.tableAttendees.setHorizontalHeaderLabels(["ID Eventbrite", "Prénom", "Nom", "Rôle", "Compagnie", "Imprimé?"])
		# Connexion des signaux
		self.btnConnectUser.clicked.connect(self.connect_user)
		self.comboOrg.currentIndexChanged.connect(self.load_events_list)
		self.btnLoadEvent.clicked.connect(self.load_event_data)
		self.tableAttendees.cellChanged.connect(self.update_attendee_from_cells)
		self.btnSaveSession.clicked.connect(self.quicksave_session)
		self.btnLoadSession.clicked.connect(self.quickload_session)

	# Connecte un utilisateur à partir de la clé d'API entrée dans le LineEdit.
	def connect_user(self):
		self.groupAuth.setEnabled(False)
		self.groupEvent.setEnabled(False)
		self.tableAttendees.clearContents()
		self.lblConnectedUser.setText(f"Connexion...")
		self.repaint()
		# Authentifier avec la clé de API.
		self.eventbrite.connect(self.lineApiKey.text())
		if self.eventbrite.user is not None and self.eventbrite.user.ok:
			self.lblConnectedUser.setText(f"Connecté en tant que {self.eventbrite.user['name']}")
			self.groupEvent.setEnabled(True)
			self.groupAuth.setEnabled(True)
		else:
			self.groupAuth.setEnabled(True)
			self.lblConnectedUser.setText("Erreur de connexion")
			return

		# Éviter les signaux redondants.
		blocker = QSignalBlocker(self.comboOrg)
		# Charger la liste des organisations existante pour l'utilisateur connecté
		self.comboOrg.clear()
		for org in self.eventbrite.list_orgs():
			item_text = org["name"]
			item_data = int(org["id"])
			self.comboOrg.addItem(item_text, item_data)
		# Sélectionner par défaut la première organisation.
		self.comboOrg.setCurrentIndex(0)
		self.load_events_list()

	# Charge la liste d'événements associée à l'organisation sélectionnée dans le ComboBox.
	def load_events_list(self):
		selected_org = self.comboOrg.currentData()
		self.comboEvent.clear()
		events = self.eventbrite.list_events(selected_org)
		for ev in events:
			item_text = ev["name"]["text"]
			item_data = int(ev["id"])
			self.comboEvent.addItem(item_text, item_data)
		self.comboEvent.setCurrentIndex(0)

	# Charge les données de base d'un événement ainsi que sa liste de participant.
	def load_event_data(self):
		self.sync_data_from_table()
		# Charger les infos de l'événements
		new_event_id = int(self.comboEvent.currentData())
		self.eventbrite.load_event(new_event_id)
		event = self.eventbrite.event
		self.lblEventID.setText(event["id"])
		self.lblEventName.setText(event["name"]["text"])
		self.lblEventDate.setText(event["start"]["local"])
		# Charger et mettre à jour les participants
		new_attendees = self.eventbrite.download_attendees()
		self.eventbrite.update_attendees(new_attendees, self.chkOverwrite.isChecked())
		self.fill_table()

	def fill_table(self):
		# D'abord déconnecter le signal qui est redondant (voir récursif)
		blocker = QSignalBlocker(self.tableAttendees)
		# Mettre à jour la table de participants
		table = self.tableAttendees
		table.clearContents()
		table.setRowCount(len(self.eventbrite.attendees))
		for index, att in enumerate(self.eventbrite.attendees.values()):
			# Configurer la première colonne (le ID) pour être lecture seule, vu que briserait trop de chose de laisser le ID éditable.
			idCellItem = QTableWidgetItem(att.attendee_id)
			idCellItem.setFlags(idCellItem.flags() & ~Qt.ItemIsEditable)
			table.setItem(index, 0, idCellItem)
			table.setItem(index, 1, QTableWidgetItem(att.first_name))
			table.setItem(index, 2, QTableWidgetItem(att.last_name))
			table.setItem(index, 3, QTableWidgetItem(att.position))
			table.setItem(index, 4, QTableWidgetItem(att.company))
			# La dernière colonne est un combo box indiquant le status d'impression
			printedCell = QComboBox()
			printedCell.addItems(["Oui", "Non", "Exclu"])
			printedCell.setCurrentIndex(att.printing_status)
			table.setCellWidget(index, 5, printedCell)

	def update_attendee_from_cells(self, row, column):
		table = self.tableAttendees
		attendee_id = table.item(row, 0).text()
		attendee = self.eventbrite.attendees.get(attendee_id, None)
		if attendee is None:
			logging.warning(f"Attendee {attendee_id} is in table but not in Eventbrite data.")
			return
		attendee.first_name = table.item(row, 1).text()
		attendee.last_name = table.item(row, 2).text()
		attendee.position = table.item(row, 3).text()
		attendee.company = table.item(row, 4).text()
		attendee.printing_status = Print(table.cellWidget(row, 5).currentIndex())

	def sync_data_from_table(self):
		for i in range(self.tableAttendees.rowCount()):
			cell_item = self.tableAttendees.item(i, 0)
			# Rien à faire si la cellule n'existe pas (différente de vide)
			if cell_item is not None:
				self.update_attendee_from_cells(i, 0)

	def quicksave_session(self):
		self.sync_data_from_table()
		session_data = {
			"api_key": self.eventbrite.api.oauth_token
		}

		try:
			os.mkdir("sessions/")
		except:
			pass
		backup_filename = os.path.join(
			"sessions",
			time.strftime("%Y%m%d_%H%M%S_quicksave.json", time.localtime())
		)
		json.dump(session_data, open("sessions/quicksave.json", "w"), indent=2)
		shutil.copy2("sessions/quicksave.json", backup_filename)
		logging.info(f"Saved session to sessions/quicksave.json")

	def quickload_session(self):
		try:
			session_data = json.load(open("sessions/quicksave.json"))
			logging.info(f"Loaded session from sessions/quicksave.json")
			self.lineApiKey.setText(session_data["api_key"])
			self.lineApiKey.repaint()
			self.connect_user()
		except FileNotFoundError:
			logging.error(f"Could not load session from sessions/quicksave.json")

