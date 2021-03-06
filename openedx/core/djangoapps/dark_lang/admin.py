"""
Admin site bindings for dark_lang
"""

from django.contrib import admin

from config_models.admin import ConfigurationModelAdmin
from openedx.core.djangoapps.dark_lang.models import DarkLangConfig

admin.site.register(DarkLangConfig, ConfigurationModelAdmin)
