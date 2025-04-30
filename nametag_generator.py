import sys
import logging
from collections import namedtuple
import os
import inspect

import docxtpl
import qrcode
import png

from utils import *


TemplateVariableValue = namedtuple("TemplateVariableValue", """
	is_key
	value
""")

class NametagGenerator:
	@staticmethod
	def render_step(func):
		func.is_custom_step = True
		return func

	def __init__(self):
		self.doc = None
		self.reset_basic_context()
		
		funcs = inspect.getmembers(
			self,
			lambda fn: hasattr(fn, "is_custom_step") and fn.is_custom_step
		)
		self.render_step_functions = dict(funcs)

	def load_template(self, filepath):
		self.doc = docxtpl.DocxTemplate(filepath)
		logging.info(f"Loaded Word template {filepath}")

	def get_template_variables(self):
		return self.doc.get_undeclared_template_variables()

	def get_custom_render_steps(self):
		return list(self.render_step_functions.keys())

	def reset_basic_context(self):
		self.basic_context = {}

	def add_context_entry(self, variable_name, is_key, value):
		self.basic_context[variable_name] = TemplateVariableValue(is_key, value)

	def generate_nametag(self, data, filepath, render_steps=[]):
		self.doc.reset_replacements()

		for step in render_steps:
			self.render_step_functions[step](data, filepath)

		context = {}
		for k, v in self.basic_context.items():
			context[k] = data[v.value] if v.is_key else v.value
		self.doc.render(context, autoescape=True)
		self.doc.save(filepath)
		logging.info(f"Generated nametag {filepath}")

	def generate_qrcode(self, data, filepath):
		img = qrcode.make(data)
		img.save(filepath)
		logging.info(f"Generated QR code {filepath}")

	@render_step
	def add_qr_code(self, data, filepath):
		img_filepath = os.path.splitext(filepath)[0] + "_QR.png"
		self.generate_qrcode(data["barcode"], img_filepath)
		# replace_pic fonctionne de façon un peu particulière, il faut utiliser le champ 'name' dans le document.xml à l'intérieur du docx.
		self.doc.replace_pic("Picture 4", img_filepath)

