import xmlrpc.client
import json
import re
import pandas as pd
from pydantic import validate_call, StringConstraints
from typing import List, Union, Optional, Annotated, Literal
import logging
from pprint import pformat
from keypy.core.exceptions import ConnectionFailed, AuthenticationFailed

validate_config = {
    "arbitrary_types_allowed": True,
    "validate_default": True
}
# custom types
NonEmptyStr=Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]
OdooPermission=Literal["read", "write", "create", "unlink"]

class OdooConnection():
    """
    Wrapper class around XML-RPC API endpoint for Odoo.

    Attributes:
        url (str): Odoo server URL
        db (str): Odoo database name
        username (str): Odoo username
        password (str): Odoo password
        uid (str): User ID in Odoo based on username
        common (xmlrpc.client.ServerProxy): common endpoint of Odoo's XML-RPC endpoint
        models (xmlrpc.client.ServerProxy): models endpoint of Odoo's XML-RPC endpoint

    Methods:
        _execute_kw(): Generic wrapper around execute_kw() method
        get_model_fields: Get metadata about fields in a model
        search_model_ids(): Find record IDs based on search criteria
        get_model_data(): Read data from model based on search criteria
    """

    _description = "Wrapper class around XML-RPC API endpoint for Odoo"

    @validate_call(config = validate_config)
    def __init__(self, url: NonEmptyStr, db: NonEmptyStr, username: NonEmptyStr, password: NonEmptyStr):
        """
        Initialize the Odoo API wrapper by

        Args:
            url: Odoo server URL
            db: Odoo database name
            username: Odoo username
            password: Odoo password

        Raises:
            ConnectionError: Connection to Odoo's XML-RPC endpoint failed.
        """

        logging.info("Connecting to Odoo API.")

        self.url = url
        logging.info(f"OdooConnection: url set to {url}")
        self.db = db
        logging.info(f"OdooConnection: db set to {db}")
        self.username = username
        logging.info(f"OdooConnection: username set to {username}")
        self.password = password
        logging.info("OdooConnection: password set (hidden for security)")

        try:
            self.common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(url))
            self.uid = self.common.authenticate(db, username, password, {})
            self.models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(url))
        except (ConnectionRefusedError, TimeoutError):
            raise ConnectionFailed("Network connectivity issue") from None
        except (xmlrpc.client.ProtocolError, ValueError):
            raise ConnectionError("Failed to connect to Odoo: Invalid URL or endpoint")
        except xmlrpc.client.Fault as e:
            raise AuthenticationFailed(e.faultString) from e
        except Exception as e:
            raise ConnectionError("Unexpected error: {}".format(e))
        
        # actually xmlrpc connection doesn't necessarily error out
        # if uid returned is null, then connection failed
        if self.uid==None:
            raise AuthenticationFailed("Could not resolve a valid Odoo user given the input parameters.") from None

        logging.info("Successfully connected to Odoo API.")

    @validate_call(config = validate_config)
    def _execute_kw(self, data_model: NonEmptyStr, method: str, args: Optional[list] = None, kwargs: Optional[dict] = None) -> Union[List[dict], dict, List[int], int, bool, str]:
        """
        Execute a low-level Odoo API call using the `execute_kw` method.

        Args:
            data_model (str): The name of the Odoo model to access.
            method (str): The name of the method to call on the model.
            args (list, optional): A list of arguments to pass to the method.
            kwargs (dict, optional): A dictionary of keyword arguments to pass to the method.

        Returns:
            Union[List[dict], dict, List[int], int, bool, str]: The result of the Odoo API call.
                * List of dictionaries: A list of records in the Odoo model.
                * Dictionary: A single record in the Odoo model.
                * Integer/list of integers: The ID(s) of a newly created record.
                * Boolean: A success or failure indicator.
                * String: An error message or exception.

        Note:
            This method is intended for internal use and should not be accessed directly except for testing purposes.
        """
        if not args:
            args = []
        if not kwargs:
            kwargs = {}
        return self.models.execute_kw(self.db, self.uid, self.password, data_model, method, args, kwargs)

    @validate_call(config = validate_config)
    def search_model_ids(self, data_model: NonEmptyStr, domain: Optional[List[tuple]] = None, offset: Optional[int] = None, limit: Optional[int] = None) -> List[int]:
        """
        Search for records in Odoo based on a domain (search criteria)

        Args:
            data_model (str): Odoo model name (e.g. 'res.partner')
            domain (List[tuple], optional): Filter condition(s) (e.g. [('name', '=', 'John')])
            offset (int, optional): Number of records to skip (e.g. 10)
            limit (int, optional): Number of records to return (e.g. 5)

        Returns:
            List of record IDs
        """
        params = {}
        if offset:
            params["offset"] = offset
        if limit:
            params["limit"] = limit
        filters = []
        if domain:
            filters = [domain]
        return self.models.execute_kw(self.db, self.uid, self.password, data_model, 'search', filters, params)

    @validate_call(config = validate_config)
    def get_model_fields(self, data_model: NonEmptyStr, fields: Optional[List[str]] = None, attributes: Optional[List[str]] = None) -> dict:
        """
        Returns metadata about fields in Odoo models

        Args:
            data_model (str): Odoo model name (e.g. 'res.partner')
            fields (List[str], optional): List of fields for which to retrieve metadata (e.g. ["id", "name"])
            attributes (List[str], optional): List of metadata properties to get back (e.g. ["name", "string", "help", "type"])

        Returns:
            dict: Dictionary representing the properties of the fields in the model
                * the keys being the name of the fields.
                * the values being the metadata about each field as a dictionary.
        """
        params = {}
        if attributes:
            params["attributes"] = attributes
        filters = []
        if fields:
            filters = [fields]

        return self._execute_kw(data_model, "fields_get", filters, params)

    @validate_call(config = validate_config)
    def get_model_data(self, data_model: NonEmptyStr, domain: Optional[List[tuple]] = None, fields: Optional[List[str]] = None, offset: Optional[int] = None, limit: Optional[int] = None) -> List[dict]:
        """
        Search for records in Odoo based on a domain (search criteria)

        Args:
            data_model (str): Odoo model name (e.g. 'res.partner')
            domain (List[tuple], optional): Filter condition(s) (e.g. [('name', '=', 'John')])
            fields (List[str], optional): List of fields for which to retrieve data (e.g. ["id", "name"])
            offset (int, optional): Number of records to skip (e.g. 10)
            limit (int, optional): Number of records to return (e.g. 5)

        Returns:
            List[dict]: List of records based on query criteria
        """
        params = {}
        if offset:
            params["offset"] = offset
        if limit:
            params["limit"] = limit
        if fields:
            params["fields"] = fields
        filters = []
        if domain:
            filters = [domain]
        return self.models.execute_kw(self.db, self.uid, self.password, data_model, 'search_read', filters, params)

    @validate_call(config = validate_config)
    def create_model_record(self, data_model: NonEmptyStr, data: Union[List[dict], dict]) -> Union[List[int], int]:
        """
        Creates a new record in Odoo

        Args:
            data_model (str): Odoo model name (e.g. 'res.partner')
            data (dict or list of dicts): Dictionary(ies) with key-value pairs for the properties to populate (e.g. {"name": "John Doe", "address": "Doe street 41"})

        Returns:
            Union[List[int], int]: ID(s) of the newly created record(s)
        """
        if isinstance(data, dict):
            data = [data]

        return self._execute_kw(data_model = data_model, method = 'create', args = data)

    @validate_call(config = validate_config)
    def update_model_record(self, data_model: NonEmptyStr, id: int, data: dict):
        """
        Update an existing record in Odoo

        :param data_model: Odoo model name (e.g. 'res.partner')
        :param id: ID of the record to update
        :param data: Dictionary containing updated record data (fields and values)
        :return: True if the update was successful
        """
        return self.models.execute_kw(self.db, self.uid, self.password, data_model, 'write', [id, data])

    @validate_call(config = validate_config)
    def check_access(self, data_model: NonEmptyStr, access:OdooPermission) -> bool :
        """
        Tests if user connect has permission over the target data model.

        :param data_model: Odoo model name (e.g. 'res.partner')
        :param access: type of access to check for
        :return: True if the access exists
        """
        return self.models.execute_kw(self.db, self.uid, self.password, data_model, 'check_access_rights', [access], {'raise_exception': False})