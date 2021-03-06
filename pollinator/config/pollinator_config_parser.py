import json
import jsonschema
import jsonmerge
from pprint import pprint
from .config import Config
from pollinator.exceptions import PollinatorPlatformConfigError, PollinatorPlatformConfigErrorList, PollinatorPlatformConfigAWSError
from collections import abc
from functools import reduce
import operator

PLATFORM_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "executor": {"type": "string", "enum": ["local", "celery", "LocalExecutor", "CeleryExecutor"]},
        "include_hive": {"type": "boolean"},
        "include_aws": {"type": "boolean"},
        "include_examples": {"type": "boolean"},
    },
    "required": ["name", "executor"]
}

AWS_SCHEMA = {
    "type": "object",
    "properties": {
        "access_key_id": {"type": "string"},
        "secret_access_key": {"type": "string"},
        "region": {"type": "string"},
        "output": {"type": "string"}
    },
    "required": ["access_key_id", "secret_access_key"]
}

POSTGRES_SCHEMA = {
    "type": "object",
    "properties": {
        "user": {"type": "string"},
        "password": {"type": "string"},
        "db": {"type": "string"},
        "internal_port": {"type": "number"},
        "external_port": {"type": "number"}
    }
}

DOCKER_SCHEMA = {
    "type": "object",
    "properties": {
        "image_name": {"type": "string"},
        "load_pipfile": {"type": "boolean"},
        "load_requirements": {"type": "boolean"},
        "airflow_home": {"type": "string"},
        "airflow_submodules": {"type": "array","items": {"type": "string"}}
    }, 
    "required": ["image_name"]
}
AIRFLOW_USERS_SCHEMA = {
    "type": "object",
    "properties": {
        "username": {"type": "string"},
        "firstname": {"type": "string"},
        "lastname": {"type": "string"},
        "email": {"type": "string"},
        "password": {"type": "string"},
        "role": {"type": "string", "enum": ["Admin", "User", "Op", "Viewer", "Public"]}
    },
    "required": ["firstname", "lastname", "email", "password", "role", "username"]
}

AIRFLOW_SCHEMA = {
    "type": "object",
    "properties": {
        "user": {"type": "string"},
        "webserver_port": {"type": "number"},
        "webserver_internal_port": {"type": "number"},
        "webserver_external_port": {"type": "number"},
        "authentication": {"type": "boolean"},
        "email": {
            "type": "object",
            "properties": {
                "email_address": {"type": "string"},
                "password":{"type": "string"},
                "smtp_host": {"type": "string"},
                "smtp_port": {"type": "number"}
            },
            "required": ["email_address", "password", "smtp_host", "smtp_port"]
        },
        "accounts": {
            "type": "array",
            "items": AIRFLOW_USERS_SCHEMA
        }
    },
    "required": ["user"]
}

SCHEMA = {
    "type": "object",
    "properties": {
        "platform": PLATFORM_SCHEMA,
        "aws": AWS_SCHEMA,
        "postgres" : POSTGRES_SCHEMA,
        "docker": DOCKER_SCHEMA,
        "airflow": AIRFLOW_SCHEMA
    },
    "required": ["platform", "airflow", "docker"]
}

class PollinatorConfigParser():

    def __init__(self, config_file):
        self.config_file = config_file
        self.locale = None
        self.__schema = SCHEMA
        self.is_validated = False
        self.contain_errors = False
        self.validation_errors = []
        self.invalid_params_objs = []
        self.default_config_file = Config.PLATFORM_DEFAULT_CONFIG_PATH

        self.__load_configs()
        self.__apply_defaults()
        self.__validate()

    def __load_configs(self):
        with open(self.config_file) as config_file_handler:
            config_str = config_file_handler.read()
            self.config = json.loads(config_str)
        
        with open(self.default_config_file) as default_config_file_handler:
            default_config_str = default_config_file_handler.read()
            self.default_config = json.loads(default_config_str)

    def __apply_defaults(self):
        self.config = jsonmerge.merge(self.default_config, self.config)

        # Check for config settings
        include_aws = self.config['platform']['include_aws']
        if include_aws and 'aws' not in self.config:
            print('No aws credentials supplied looking for credentials on local system!')
            self.set_aws_credentials()
    
    def set_aws_credentials(self):
        config = Config()
        try:
            aws_credentials = config.get_aws_credentials()
            print('Found AWS credentials on local system! Using local system AWS credentials')
            self.config['aws'] = aws_credentials
        except:
            raise PollinatorPlatformConfigAWSError('No AWS Credentials Found or invalid aws settings! Please provide credentials')
        
    def __validate(self):
        validation = jsonschema.Draft7Validator(self.__schema)
        for error in sorted(validation.iter_errors(self.config), key=str):
            param = error.message.split("'")[1]
            hiearchy = list(error.relative_path)
            hiearchy.append(param)
            self.contain_errors =  True
            self.invalid_params_objs.append({param : hiearchy})
            self.validation_errors.append(PollinatorPlatformConfigError(error.relative_path, error.message).message)
        self.is_validated = True
        if self.errors:
            raise PollinatorPlatformConfigErrorList(self.validation_errors)

    @property
    def invalid_params(self):
        return self.invalid_params_objs
        
    @property
    def errors(self):
        return self.validation_errors

    def get_property(self,  property_name, locale=None):
        config_dict = self.config
        locale = locale or self.locale
        if locale is not None:    
            if locale not in config_dict.keys(): # we don't want KeyError
                return None  # just return None if not found
            config_dict = config_dict[locale]

        if property_name not in config_dict.keys():
            return None
        return config_dict[property_name]