import os
from datetime import datetime
import dateutil.parser


def makeDirIfNotExist(path):
    if not os.path.exists(path):
        os.makedirs(path)


def date_hook(json_dict):
    for key, value in json_dict.items():
        try:
            json_dict[key] = dateutil.parser.isoparse(value)
        except:
            pass
    return json_dict


def data_serial(obj):
    if isinstance(obj, (datetime)):
        return obj.isoformat()
    raise TypeError("Type %s not serializable" % type(obj))
