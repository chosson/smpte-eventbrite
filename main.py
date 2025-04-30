import sys
import os
import json
import logging
import time


from PySide6.QtWidgets import QApplication

import main_window
from utils import *


def main():
	# Les messages de niveau INFO et plus sérieux sont affichés dans la console, tous les messages sont écrits dans le fichier.
	setup_basic_logging("logs", logging.INFO, logging.DEBUG)

	app = QApplication(sys.argv)
	win = main_window.MainWindow()
	win.show()
	logging.info("Window loaded")
	app.exec()

if __name__ == "__main__":
	main()
