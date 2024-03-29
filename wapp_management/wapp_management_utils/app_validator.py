import os
import re
from katana.native.wapp_management.wapp_management_utils.wapp_mgmt_utils import get_version_list, check_against_version_list
from katana.utils.directory_traversal_utils import join_path, get_sub_dirs_and_files, \
    get_paths_of_subfiles, get_sub_folders
from katana.utils.json_utils import read_json_data
from katana.utils.navigator_util import Navigator


class AppValidator:

    def __init__(self, filepath):
        """
        :param filepath: Path to the root directory of the app being installed

        self.navigator: Navigator() onject
        self.app_name: Name of the actual app directory.
        self.path_to_app: Path to the actual app directory
        self.wf_config_file: Path to the app's wf_config file
        self.urls_inclusions: List of ursl that need o be included in main urls.py
        self.mandatory_fields: Mandatory fields necessary in wf_config.json
        self.wapp_data: All data in the wf_config.json file
        self.django_based: True indicates that this app uses new Katana API. False indicates that
                           app still uses the old Katana API
        """
        self.navigator = Navigator()
        self.app_name = get_sub_folders(join_path(filepath, "warriorframework_py3", "katana", "katana.wapps"))[0]
        self.path_to_app = join_path(filepath, "warriorframework_py3", "katana", "katana.wapps", self.app_name)
        self.wf_config_file = join_path(self.path_to_app, "wf_config.json")
        self.urls_inclusions = []
        self.mandatory_fields = ["app", "version", "warrior-compatibility", "warrior-incompatibility"]
        self.wapp_data = read_json_data(self.wf_config_file)
        self.django_based = False if "pure_django" not in self.wapp_data or not self.wapp_data["pure_django"] else True

    def is_valid(self):
        output = {"status": True, "message": ""}
        if os.path.exists(self.wf_config_file):
            if self.wapp_data is not None:
                for field in self.mandatory_fields:
                    if output["status"] and field not in self.wapp_data:
                        output["status"] = False
                        output["message"] = "wf_config.json is not in the correct format."
                        print("-- An Error Occurred -- {0}".format(output["message"]))

                if output["status"]:
                    output = self.__verify_app_details(self.wapp_data["app"])

                # validate version compatibility
                if output["status"]:
                    output = self.__is_compatible(self.wapp_data)

                # validate databases if any
                if output["status"] and "database" in self.wapp_data:
                    if isinstance(self.wapp_data["database"], list):
                        for db_details in self.wapp_data["database"]:
                            if output["status"]:
                                output = self.__verify_db_details(db_details)
                    else:
                        output = self.__verify_db_details(self.wapp_data["database"])
            else:
                output["status"] = False
                output["message"] = "wf_config.json is not in the correct format."
                print("-- An Error Occurred -- {0}".format(output["message"]))

            if output["status"]:
                output = self.__validate_static_directory()
        else:
            output["status"] = False
            output["message"] = "wf_config.json does not exist."
            print("-- An Error Occurred -- {0}".format(output["message"]))
        return output

    def __verify_app_details(self, app_details):
        output = {"status": True, "message": ""}
        if "name" not in app_details or "url" not in app_details or "include" not in app_details:
            print("-- An Error Occurred -- wf_config.json file is not in the correct format.")
            output["status"] = False
        else:
            self.urls_inclusions.append("url(r'^" + app_details["url"] +
                                        "', include('" + app_details["include"] + "')),")
            path_dir = app_details["include"].split(".")
            path_urls = ""
            for d in range(2, len(path_dir)):
                path_urls += os.sep + path_dir[d]
            path_urls = path_urls.strip(os.sep)
            path_urls += ".py"
            path_to_urls_abs = join_path(self.path_to_app, path_urls)
            if not os.path.isfile(path_to_urls_abs):
                output["status"] = False
                output["message"] = "Package {0} does not exist.".format(app_details["include"])
                print("-- An Error Occurred -- {0}".format(output["message"]))
        return output

    def __is_compatible(self, data):
        output = {"status": True, "message": ""}
        warrior_version = self.navigator.get_wf_version()
        all_warrior_versions = self.navigator.get_all_wf_versions()
        allowed, bounds, err_alwd = get_version_list(data[self.mandatory_fields[2]], all_warrior_versions)
        disallowed, excluded_bounds, err_disalwd = get_version_list(data[self.mandatory_fields[3]], all_warrior_versions)

        in_allowed = check_against_version_list(warrior_version, allowed, bounds)
        in_disallowed = check_against_version_list(warrior_version, disallowed, excluded_bounds)

        if not in_allowed:
            output["status"] = False
            if not err_alwd:
                output["message"] = "-- An Error Occurred -- {0} (Version: {1}) incompatible with " \
                                    "the current WarriorFramework (Version: {2})."\
                    .format(self.app_name, data["version"], warrior_version)
            else:
                output["message"] = "-- An Error Occurred -- Compatible versions could not be verified."
        elif in_disallowed:
            output["status"] = False
            output["message"] = "-- An Error Occurred -- {0} (Version: {1}) incompatible with " \
                                "the current WarriorFramework (Version: {2})." \
                .format(self.app_name, data["version"], warrior_version)
        elif not in_disallowed and err_disalwd:
            output["status"] = False
            output["message"] = "-- An Error Occurred -- Incompatible versions could not be verified."
        return output

    def __verify_db_details(self, db_details):
        output = {"status": True, "message": ""}
        for key in db_details:
            if not key.startswith(self.app_name):
                output["status"] = False
                output["message"] = "wf_config.json file is not formatted correctly"
                print("-- An Error Occurred -- {0}".format(output["message"]))
        return output

    def __validate_static_directory(self):
        output = {"status": True, "message": ""}
        if os.path.isdir(join_path(self.path_to_app, "static")):
            subs = get_sub_dirs_and_files(join_path(self.path_to_app, "static"))
            if len(subs["files"]) > 0:
                output["status"] = False
                output["message"] = "static directory does not follow the required " \
                                    "directory structure."
                print("-- An Error Occurred -- {0}".format(output["message"]))
            else:
                if not os.path.isdir(join_path(self.path_to_app, "static", self.app_name)):
                    output["status"] = False
                    output["message"] = "static directory does not follow the required " \
                                        "directory structure."
                    print("-- An Error Occurred -- {0}".format(output["message"]))
                else:
                        
                    subs_files = get_paths_of_subfiles(join_path(self.path_to_app, "static",
                                                                 self.app_name),
                                                       re.compile("\.js$"))
                    path_to_js = join_path(self.path_to_app, "static", self.app_name, "js")
                    if not self.django_based:
                        # Validates JS structure only if app uses old Katana API
                        list_of_files = ", ".join([x for x in subs_files if not x.startswith(path_to_js)])
                        if list_of_files:
                            output["status"] = False
                            output["message"] = "A .js file cannot be outside the 'js' folder. " \
                                                "List of files in non-compliance: {0}".format(list_of_files)
                            print("-- An Error Occurred -- {0}".format(output["message"]))
        return output
