# functions/utils.py
import math

def human_size(bytesize):
    if bytesize is None:
        return "Unknown"
    try:
        bytesize = int(bytesize)
    except Exception:
        return "Unknown"
    if bytesize == 0:
        return "0B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = int(math.floor(math.log(max(bytesize,1), 1024)))
    return f"{bytesize / (1024 ** i):.2f} {units[i]}"
