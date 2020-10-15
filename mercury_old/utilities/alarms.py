# Alarm definitions and functions

# Alarm trigger classifications
alarm_map = {
    'IS': lambda val, thres: val == thres,
    'NOT': lambda val, thres: val != thres,
    'GREATER': lambda val, thres: val > thres,
    'GEQ': lambda val, thres: val > thres,
    'LESS': lambda val, thres: val < thres,
    'LEQ': lambda val, thres: val <= thres,
}

