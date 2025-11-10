import importlib
from typing import Optional

import usb.core
import yaml

from thermalright_lcd_control.device_controller.display.display_device import DisplayDevice


class DeviceLoader:
    def __init__(self, config_dir: str):
        self.config_dir = config_dir

    def load_device(self) -> Optional[DisplayDevice]:
        with open(f"{self.config_dir}/device_info.yaml", "r") as config_file:
            yaml_config = yaml.load(config_file, Loader=yaml.FullLoader)
        class_name_str = yaml_config["class_name"]
        vid = yaml_config["vid"]
        pid = yaml_config["pid"]
        device = usb.core.find(idVendor=vid, idProduct=pid)
        if device is not None:
            class_name = self.load_class(class_name_str)
            return class_name(self.config_dir)
        return None

    @staticmethod
    def load_class(full_class_name: str):
        try:
            module_name, class_name = full_class_name.rsplit(".", 1)
        except ValueError:
            raise ValueError(f"Invalid name : {full_class_name} (must contain dot)")

        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError as e:
            raise ImportError(f"Impossible d’importer le module '{module_name}'") from e

        try:
            cls = getattr(module, class_name)
        except AttributeError as e:
            raise ImportError(f"Classe '{class_name}' introuvable dans '{module_name}'") from e

        return cls
