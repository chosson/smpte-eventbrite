from dataclasses import dataclass, asdict
from enum import IntEnum
import logging

from eventbrite import Eventbrite


class PrintStatus(IntEnum):
	PRINTED = 0
	UNPRINTED = 1
	EXCLUDED = 2


@dataclass
class Attendee:
	attendee_id: str
	first_name: str
	last_name: str
	email: str
	position: str
	company: str
	barcode: str
	printing_status: IntEnum
	raw_data: any

	def __getitem__(self, index):
		if index not in self.__dataclass_fields__:
			raise AttributeError(index)
		return getattr(self, index)

	def __setitem__(self, index, val):
		if index not in self.__dataclass_fields__:
			raise AttributeError(index)
		setattr(self, index, val)

	@classmethod
	def build_from_object(cls, attendee_object):
		obj = attendee_object
		return cls(
			obj["id"].strip(),
			obj["profile"]["first_name"].strip(),
			obj["profile"]["last_name"].strip(),
			obj["profile"]["email"].strip(),
			obj["profile"].get("job_title", "").strip(),
			obj["profile"].get("company", "").strip(),
			obj["barcodes"][0]["barcode"].strip(),
			PrintStatus.UNPRINTED,
			attendee_object
		)


class EventbriteManager:
	def __init__(self):
		self.api = None
		self.user = None
		self.event = None
		self.attendees = {}

	def connect(self, api_token):
		try:
			self.__init__()
			self.api = Eventbrite(api_token)
			self.user = self.api.get_user()
		except:
			logging.error("Error while parsing request to authenticate")
			self.user = None
			return
		if self.user.ok:
			logging.info(f"Logged in as {self.user['name']} ({self.user['id']})")
		else:
			logging.error(f"Error {self.user['status_code']}: {self.user['error_description']}")

	def fetch_orgs(self):
		response = self.api.get("/users/me/organizations/")
		logging.info(f"Fetched organizations for user {self.user['id']}")
		return response["organizations"]

	def fetch_events(self, org_id):
		response = self.api.get(f"/organizations/{org_id}/events/")
		logging.info(f"Fetched events list for organization {org_id}")
		return response["events"]

	def load_event(self, event_id):
		new_event = self.api.get_event(event_id)
		# Réinitialiser la liste des participants si on charge un événement différent.
		if self.event is not None and new_event["id"] != self.event["id"]:
			self.attendees.clear()
		self.event = new_event
		logging.info(f"Loaded event {self.event['name']['text']} ({event_id})")

	def download_attendees(self):
		event_id = self.event["id"]
		# Télécharger et traiter les données d'Eventbrite
		raw_attendees_data = self.api.get(f"/events/{event_id}/attendees/")["attendees"]
		loaded_attendees = {att["id"]: Attendee.build_from_object(att) for att in raw_attendees_data}
		return loaded_attendees

	def update_attendees(self, new_attendees, overwrite_profiles=False):
		# Mettre à jour la liste existante
		for att_id, att in new_attendees.items():
			# Écraser ou créer l'entrée dans le dict si applicable
			if att_id not in self.attendees:
				self.attendees[att_id] = att
			else:
				if overwrite_profiles:
					# Conserver quand même le flag d'impression complétée
					att.printing_status = self.attendees[att_id].printing_status
					self.attendees[att_id] = att

	def serialize_attendees(self):
		serialized_data = {k: asdict(v) for k, v in self.attendees.items()}
		return serialized_data

	def load_serialized_attendees(self, serialized_data):
		deserialized = {k: Attendee(**v) for k, v in serialized_data.items()}
		self.attendees = deserialized

