import sys
import logging
from collections import namedtuple

import docxtpl

from utils import *


TemplateVariableValue = namedtuple("TemplateVariableValue", """
	is_key
	value
""")

class NametagGenerator:
	def __init__(self):
		self.doc = None
		self.reset_basic_context()

	def load_template(self, filepath):
		self.doc = docxtpl.DocxTemplate(filepath)
		logging.info(f"Loaded Word template {filepath}")

	def get_template_variables(self):
		return self.doc.get_undeclared_template_variables()

	def reset_basic_context(self):
		self.basic_context = {}

	def add_context_entry(self, variable_name, is_key, value):
		self.basic_context[variable_name] = TemplateVariableValue(is_key, value)

	def auto_generate_nametag(self, data, filepath):
		context = {}
		for k, v in self.basic_context.items():
			context[k] = data[v.value] if v.is_key else v.value
		self.doc.render(context, autoescape=True)
		self.doc.save(filepath)
