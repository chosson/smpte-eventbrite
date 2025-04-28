import os
import logging
import time

from PySide6.QtCore import Qt, QSignalBlocker


def checkToBool(checkState):
	return False if checkState == Qt.Unchecked else True

def boolToCheck(boolean):
	return Qt.Checked if boolean else Qt.Unchecked

def clamp(val, lower, upper):
	return min(max(val, lower), upper)

def format_datetime(fmt="%Y%m%d_%H%M%S"):
	return time.strftime(fmt, time.localtime())

def setup_basic_logging(logs_dir, con_level, file_level=logging.DEBUG):
	# Créer le gestionnaire qui écrit dans la console.
	con_handler = logging.StreamHandler()
	con_handler.setLevel(con_level)

	# Créer le dossier de journaux s'il n'existe pas.
	if not os.path.exists(logs_dir):
		os.mkdir(logs_dir)
	# Construire le chemin du fichier selon la date et l'heure actuelle.
	filename = os.path.join(
		logs_dir,
		format_datetime() + ".log"
	)
	# Créer le gestionnaire qui écrit dans le fichier avec le nom ci-dessus.
	file_handler = logging.FileHandler(filename)
	file_handler.setLevel(file_level)

	# Configurer le format de chaque entrée dans le journal. On veut la date et l'heure du message, son niveau et le message lui-même.
	log_fmt = logging.Formatter(
		fmt="[%(asctime)s][%(levelname)-8s] %(message)s",
		datefmt="%Y-%m-%d %H:%M:%S"
	)
	con_handler.setFormatter(log_fmt)
	file_handler.setFormatter(log_fmt)

	# Ajouter nos deux handler au journaliseur par défaut.
	logging.getLogger().addHandler(con_handler)
	logging.getLogger().addHandler(file_handler)
	logging.getLogger().setLevel(logging.DEBUG)
