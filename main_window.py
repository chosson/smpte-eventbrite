import os
import sys
import json
import time
import shutil

from PySide6 import QtUiTools
from PySide6.QtCore import Qt, QSignalBlocker
from PySide6.QtWidgets import QMainWindow, QTableWidgetItem, QComboBox, QFileDialog

from utils import *
from eventbrite_manager import *


# Importation des types venant du .ui
uiclass, baseclass = QtUiTools.loadUiType("MainWindow.ui")

class MainWindow(uiclass, baseclass):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

		self.eventbrite = EventbriteManager()

		# Chargement du GUI
		self.setupUi(self)
		self.comboManualFilter.setItemData(0, "first_name")
		self.comboManualFilter.setItemData(1, "last_name")
		self.comboManualFilter.setItemData(2, "position")
		self.comboManualFilter.setItemData(3, "company")
		# Connexion des signaux
		self.btnConnectUser.clicked.connect(self.connect_user_from_input)
		self.comboOrg.currentIndexChanged.connect(self.load_events_list_from_input)
		self.btnLoadEvent.clicked.connect(self.load_event_data_from_input)
		self.tableAttendees.cellChanged.connect(self.update_attendee_from_cells)
		self.comboManualFilter.currentIndexChanged.connect(self.fill_manual_filter_table)
		self.btnApplyManualReplacement.clicked.connect(self.apply_manual_replacement)
		self.btnSaveSession.clicked.connect(self.quicksave_session)
		self.btnLoadSession.clicked.connect(self.quickload_session)

	# Connecte un utilisateur à partir de la clé d'API entrée dans le LineEdit.
	def connect_user_from_input(self):
		# Griser les boîtes et changer le texte de connexion
		self.groupAuth.setEnabled(False)
		self.groupEvent.setEnabled(False)
		self.tableAttendees.clearContents()
		self.tableAttendees.setRowCount(0)
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
		for org in self.eventbrite.fetch_orgs():
			item_text = org["name"]
			item_data = int(org["id"])
			self.comboOrg.addItem(item_text, item_data)
		# Sélectionner par défaut la première organisation.
		self.comboOrg.setCurrentIndex(0)
		self.load_events_list_from_input()

	# Charge la liste d'événements associée à l'organisation sélectionnée dans le ComboBox.
	def load_events_list_from_input(self):
		selected_org = self.comboOrg.currentData()
		self.comboEvent.clear()
		events = self.eventbrite.fetch_events(selected_org)
		for ev in events:
			item_text = ev["name"]["text"]
			item_data = int(ev["id"])
			self.comboEvent.addItem(item_text, item_data)
		self.comboEvent.setCurrentIndex(0)

	# Charge les données de base d'un événement ainsi que sa liste de participant.
	def load_event_data_from_input(self):
		self.sync_data_from_att_table()
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
		self.fill_attendees_table()

	def fill_attendees_table(self):
		# D'abord déconnecter le signal qui est redondant (voir récursif)
		blocker = QSignalBlocker(self.tableAttendees)
		# Mettre à jour la table de participants
		table = self.tableAttendees
		table.clearContents()
		# Faut désactiver le tri auto durant la modification de la table
		table.sortItems(-1)
		table.setRowCount(len(self.eventbrite.attendees))
		for i, att in enumerate(self.eventbrite.attendees.values()):
			# Les colonnes de la rangée actuelle
			table.setItem(i, 0, QTableWidgetItem(att.attendee_id))
			table.setItem(i, 1, QTableWidgetItem(att.first_name.strip()))
			table.setItem(i, 2, QTableWidgetItem(att.last_name.strip()))
			table.setItem(i, 3, QTableWidgetItem(att.position.strip()))
			table.setItem(i, 4, QTableWidgetItem(att.company.strip()))
			# La dernière colonne est un combo box indiquant le status d'impression
			printedCell = QComboBox()
			printedCell.addItems(["Oui", "Non", "Exclu"])
			printedCell.setCurrentIndex(att.printing_status)
			table.setCellWidget(i, 5, printedCell)
			# Configurer la première colonne (le ID) pour être lecture seule, vu que briserait trop de chose de laisser le ID éditable.
			table.item(i, 0).setFlags(table.item(i, 0).flags() & ~Qt.ItemIsEditable)
		table.sortItems(0)

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
		attendee.printing_status = PrintStatus(table.cellWidget(row, 5).currentIndex())

	def sync_data_from_att_table(self):
		for i in range(self.tableAttendees.rowCount()):
			cell_item = self.tableAttendees.item(i, 0)
			# Rien à faire si la cellule n'existe pas (différente de vide)
			if cell_item is not None:
				self.update_attendee_from_cells(i, 0)

	def fill_manual_filter_table(self):
		# Le 'data' du combobox est le nom du champs dans le dataclass Attendee
		prop = self.comboManualFilter.currentData()
		if prop is None:
			self.tableManualFilter.clearContents()
			self.tableManualFilter.setRowCount(0)
			return

		values = {}
		for att_id, att in self.eventbrite.attendees.items():
			if att[prop] not in values:
				values[att[prop]] = 0
			values[att[prop]] += 1

		table = self.tableManualFilter
		table.clearContents()
		table.setRowCount(len(values))
		# Faut désactiver le tri auto durant la modification de la table
		table.sortItems(-1)
		for i, co in enumerate(values.items()):
			name, num_atts = co
			table.setItem(i, 0, QTableWidgetItem(name.strip()))
			table.setItem(i, 1, QTableWidgetItem(str(num_atts)))
			table.setItem(i, 2, QTableWidgetItem(""))
			# Seulement la valeur de remplacement doit être éditable.
			table.item(i, 0).setFlags(table.item(i, 0).flags() & ~Qt.ItemIsEditable)
			table.item(i, 1).setFlags(table.item(i, 0).flags() & ~Qt.ItemIsEditable)
		table.sortItems(0)

	def apply_manual_replacement(self):
		# Le 'data' du combobox est le nom du champs dans le dataclass Attendee
		prop = self.comboManualFilter.currentData()

		table = self.tableManualFilter
		# Faut désactiver le tri auto durant la modification de la table
		table.sortItems(-1)
		for i in range(table.rowCount()):
			name_cell = table.item(i, 0)
			replace_cell = table.item(i, 2)
			# Laisser la cellule de remplacement vide ne fait aucun remplacement.
			if replace_cell is None or replace_cell.text().strip() == "":
				continue
			for att in self.eventbrite.attendees.values():
				if att[prop] == name_cell.text().strip():
					att[prop] = replace_cell.text().strip()
		# Plus fiable de reconstruire les tables, même si un peu lent.
		self.fill_attendees_table()
		self.fill_manual_filter_table()

	def quicksave_session(self):
		# Syncro avec la table (juste au cas)
		self.sync_data_from_att_table()
		session_data = {
			"api_key": self.eventbrite.api.oauth_token,
			"event": self.eventbrite.event,
			"attendees": self.eventbrite.serialize_attendees()
		}

		mkdir_if_not_there("sessions/")
		backup_filename = f"sessions/{format_datetime()}_quicksave.json"
		json.dump(session_data, open("sessions/quicksave.json", "w"), indent=2)
		shutil.copy2("sessions/quicksave.json", backup_filename)
		logging.info(f"Saved session to sessions/quicksave.json")

	def quickload_session(self):
		try:
			session_data = json.load(open("sessions/quicksave.json"))
			logging.info(f"Loaded session from sessions/quicksave.json")
			self.lineApiKey.setText(session_data["api_key"])
			self.lineApiKey.repaint()
			self.connect_user_from_input()
			for i in range(self.comboOrg.count()):
				if self.comboOrg.itemData(i) == int(session_data["event"]["organization_id"]):
					self.comboOrg.setCurrentIndex(i)
					break
			for i in range(self.comboEvent.count()):
				if self.comboEvent.itemData(i) == int(session_data["event"]["id"]):
					self.comboEvent.setCurrentIndex(i)
					break
			self.eventbrite.event = session_data["event"]
			self.eventbrite.load_serialized_attendees(session_data["attendees"])
			self.fill_attendees_table()
			self.comboManualFilter.setCurrentIndex(-1)
		except FileNotFoundError:
			logging.error(f"Could not load session from sessions/quicksave.json")

